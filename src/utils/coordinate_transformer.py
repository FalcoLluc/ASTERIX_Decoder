import math
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class WGS84Coordinates:
    """WGS-84 Geodesic coordinates (latitude, longitude, height)"""
    lat: float  # Latitude in radians
    lon: float  # Longitude in radians
    height: float  # Height in meters


@dataclass
class CartesianCoordinates:
    """Cartesian coordinates (X, Y, Z)"""
    x: float  # X in meters
    y: float  # Y in meters
    z: float  # Z in meters


@dataclass
class PolarCoordinates:
    """Polar coordinates (rho, theta, elevation)"""
    rho: float  # Range in meters
    theta: float  # Azimuth in radians
    elevation: float = 0.0  # Elevation in radians


class CoordinateTransformer:
    """
    Coordinate transformation utilities for ASTERIX radar data.
    Implements transformations according to EUROCONTROL TransLib specifications.
    """

    # WGS-84 ellipsoid parameters
    A = 6378137.0  # Semi-major axis (meters)
    B = 6356752.3142  # Semi-minor axis (meters)
    E2 = 0.00669437999013  # Eccentricity squared

    # Conversion constants
    METERS_TO_FEET = 3.28084
    FEET_TO_METERS = 0.3048
    METERS_TO_NM = 1 / 1852.0
    NM_TO_METERS = 1852.0
    DEGS_TO_RADS = math.pi / 180.0
    RADS_TO_DEGS = 180.0 / math.pi

    # Numerical precision
    ALMOST_ZERO = 1e-10
    REQUIRED_PRECISION = 1e-8

    def __init__(self, radar_lat_deg: float, radar_lon_deg: float, radar_height_m: float):
        """
        Initialize coordinate transformer for a specific radar.

        Args:
            radar_lat_deg: Radar latitude in degrees
            radar_lon_deg: Radar longitude in degrees
            radar_height_m: Radar height in meters (antenna height above ground + ground elevation)
        """
        self.radar_position = WGS84Coordinates(
            lat=radar_lat_deg * self.DEGS_TO_RADS,
            lon=radar_lon_deg * self.DEGS_TO_RADS,
            height=radar_height_m
        )

        # Pre-calculate transformation matrices for radar
        self._radar_translation_matrix = self._calculate_translation_matrix(self.radar_position)
        self._radar_rotation_matrix = self._calculate_rotation_matrix(
            self.radar_position.lat,
            self.radar_position.lon
        )

    @staticmethod
    def _calculate_rotation_matrix(lat: float, lon: float) -> np.ndarray:
        """
        Calculate rotation matrix for coordinate transformation.

        Args:
            lat: Latitude in radians
            lon: Longitude in radians

        Returns:
            3x3 rotation matrix
        """
        return np.array([
            [-math.sin(lon), math.cos(lon), 0],
            [-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)],
            [math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)]
        ])

    def _calculate_translation_matrix(self, coords: WGS84Coordinates) -> np.ndarray:
        """
        Calculate translation vector for coordinate transformation.

        Args:
            coords: WGS-84 coordinates

        Returns:
            3x1 translation vector
        """
        nu = self.A / math.sqrt(1 - self.E2 * math.sin(coords.lat) ** 2)

        return np.array([
            [(nu + coords.height) * math.cos(coords.lat) * math.cos(coords.lon)],
            [(nu + coords.height) * math.cos(coords.lat) * math.sin(coords.lon)],
            [(nu * (1 - self.E2) + coords.height) * math.sin(coords.lat)]
        ])

    def polar_to_cartesian_local(self, polar: PolarCoordinates) -> CartesianCoordinates:
        """
        Convert radar spherical (polar) coordinates to radar local cartesian.

        Args:
            polar: Polar coordinates (rho in meters, theta and elevation in radians)

        Returns:
            Local cartesian coordinates (X, Y, Z in meters)
        """
        x = polar.rho * math.cos(polar.elevation) * math.sin(polar.theta)
        y = polar.rho * math.cos(polar.elevation) * math.cos(polar.theta)
        z = polar.rho * math.sin(polar.elevation)

        return CartesianCoordinates(x=x, y=y, z=z)

    def cartesian_local_to_geocentric(self, local: CartesianCoordinates) -> CartesianCoordinates:
        """
        Convert radar local cartesian to geocentric cartesian coordinates.

        Args:
            local: Radar local cartesian coordinates (X, Y, Z in meters)

        Returns:
            Geocentric cartesian coordinates (X, Y, Z in meters)
        """
        # Create input vector
        input_vector = np.array([[local.x], [local.y], [local.z]])

        # Apply transformation: geocentric = R^T * local + T
        result = self._radar_rotation_matrix.T @ input_vector + self._radar_translation_matrix

        return CartesianCoordinates(
            x=result[0, 0],
            y=result[1, 0],
            z=result[2, 0]
        )

    def geocentric_to_geodesic(self, geocentric: CartesianCoordinates) -> WGS84Coordinates:
        """
        Convert geocentric cartesian to WGS-84 geodesic coordinates.
        Uses iterative method from EUROCONTROL TransLib.

        Args:
            geocentric: Geocentric cartesian coordinates (X, Y, Z in meters)

        Returns:
            WGS-84 coordinates (lat, lon in radians, height in meters)
        """
        # Handle special case: point at or near Earth's center
        if abs(geocentric.x) < self.ALMOST_ZERO and abs(geocentric.y) < self.ALMOST_ZERO:
            if abs(geocentric.z) < self.ALMOST_ZERO:
                lat = math.pi / 2.0
            else:
                lat = (math.pi / 2.0) * ((geocentric.z / abs(geocentric.z)) + 0.5)
            lon = 0.0
            height = abs(geocentric.z) - self.B
            return WGS84Coordinates(lat=lat, lon=lon, height=height)

        # Calculate distance in XY plane
        d_xy = math.sqrt(geocentric.x ** 2 + geocentric.y ** 2)

        # Initial latitude estimate (formula 20 from TransLib)
        lat = math.atan(
            (geocentric.z / d_xy) /
            (1 - (self.A * self.E2) / math.sqrt(d_xy ** 2 + geocentric.z ** 2))
        )

        # Calculate nu (radius of curvature in prime vertical)
        nu = self.A / math.sqrt(1 - self.E2 * math.sin(lat) ** 2)

        # Initial height estimate
        height = (d_xy / math.cos(lat)) - nu

        # Iterative refinement (formula 20b)
        lat_prev = lat + 0.1 if lat >= 0 else lat - 0.1
        loop_count = 0

        while abs(lat - lat_prev) > self.REQUIRED_PRECISION and loop_count < 50:
            loop_count += 1
            lat_prev = lat

            lat = math.atan(
                (geocentric.z * (1 + height / nu)) /
                (d_xy * ((1 - self.E2) + (height / nu)))
            )

            nu = self.A / math.sqrt(1 - self.E2 * math.sin(lat) ** 2)
            height = d_xy / math.cos(lat) - nu

        # Calculate longitude
        lon = math.atan2(geocentric.y, geocentric.x)

        return WGS84Coordinates(lat=lat, lon=lon, height=height)

    def polar_to_wgs84(self, rho_nm: float, theta_deg: float, elevation_deg: float = 0.0) -> Tuple[float, float, float]:
        """
        Complete transformation chain: Polar → WGS-84
        This is the main method to use for CAT048 radar data.

        Args:
            rho_nm: Range in nautical miles
            theta_deg: Azimuth in degrees (0° = North, clockwise)
            elevation_deg: Elevation angle in degrees (default: 0)

        Returns:
            Tuple of (latitude_deg, longitude_deg, height_m)
        """
        # Convert inputs to SI units and radians
        polar = PolarCoordinates(
            rho=rho_nm * self.NM_TO_METERS,
            theta=theta_deg * self.DEGS_TO_RADS,
            elevation=elevation_deg * self.DEGS_TO_RADS
        )

        # Step 1: Polar → Local Cartesian
        local = self.polar_to_cartesian_local(polar)

        # Step 2: Local Cartesian → Geocentric
        geocentric = self.cartesian_local_to_geocentric(local)

        # Step 3: Geocentric → WGS-84
        wgs84 = self.geocentric_to_geodesic(geocentric)

        # Convert back to degrees
        return (
            wgs84.lat * self.RADS_TO_DEGS,
            wgs84.lon * self.RADS_TO_DEGS,
            wgs84.height
        )

    def cartesian_to_wgs84(self, x_m: float, y_m: float, z_m: float = 0.0) -> Tuple[float, float, float]:
        """
        Complete transformation chain: Cartesian Local → WGS-84
        For CAT048 data that provides cartesian coordinates.

        Args:
            x_m: X coordinate in meters (East)
            y_m: Y coordinate in meters (North)
            z_m: Z coordinate in meters (Up)

        Returns:
            Tuple of (latitude_deg, longitude_deg, height_m)
        """
        # Step 1: Local Cartesian → Geocentric
        local = CartesianCoordinates(x=x_m, y=y_m, z=z_m)
        geocentric = self.cartesian_local_to_geocentric(local)

        # Step 2: Geocentric → WGS-84
        wgs84 = self.geocentric_to_geodesic(geocentric)

        # Convert back to degrees
        return (
            wgs84.lat * self.RADS_TO_DEGS,
            wgs84.lon * self.RADS_TO_DEGS,
            wgs84.height
        )


# Barcelona radar configuration (from project specifications)
BARCELONA_RADAR_CONFIG = {
    'lat_deg': 41.300702333,  # 41° 18' 02.5284" N
    'lon_deg': 2.102058194,  # 02° 06' 07.4095" E
    'height_m': 27.257  # 2.007m terrain + 25.25m antenna
}
