"""
ASTERIX Data Exporter
---------------------
Unified exporter for CAT021 and CAT048 ASTERIX categories with QNH correction.
Optimized for memory efficiency with dtype downcasting and view-based filtering.

Column Definitions:
------------------
BP: Barometric Pressure Setting (hPa/mb)
    - CAT048 BDS 4.0: BP in mb (1 mb = 1 hPa)
    - CAT021 RE Field: BP in hPa
    - Both use same unit with 800 hPa offset applied during decoding

GS(kt): Ground Speed (knots)
    - CAT048: From TRACK_VELOCITY_POLAR (radar) or BDS 5.0 (aircraft)
    - Precedence: Radar measurement preferred, BDS 5.0 as fallback

HDG: Heading (degrees) - Radar-measured
    - CAT048 TRACK_VELOCITY_POLAR only
    - Measured by radar tracking system

MG_HDG: Magnetic Heading (degrees) - Aircraft-reported
    - CAT048 BDS 6.0 only
    - From aircraft's navigation system

TTA: True Track Angle (degrees) - Aircraft-reported
    - CAT048 BDS 5.0 only
    - Aircraft's actual track over ground
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from src.models.record import Record
from src.types.enums import CAT021ItemType, CAT048ItemType, Category
from src.utils.qnh_corrector import QNHCorrector


class AsterixExporter:
    """
    Unified exporter for all ASTERIX categories with preprocessing capabilities.
    Handles CAT021 and CAT048 records in a single DataFrame with shared and category-specific columns.

    Memory optimizations:
    - Uses dtype downcasting to reduce per-column memory footprint
    - Avoids unnecessary DataFrame copies
    - Views instead of copies where possible
    """

    ALL_COLUMNS = [
        # Common identification
        'CAT',  # ASTERIX Category (21 or 48)
        'SAC',  # System Area Code
        'SIC',  # System Identification Code
        'Time',  # Formatted time (HH:MM:SS.mmm)
        'Time_sec',  # Time in seconds from midnight

        # Position (from photo order)
        'LAT',  # Latitude (degrees)
        'LON',  # Longitude (degrees)
        'H_WGS84',  # WGS-84 height (m)
        'H(m)',  # Height in meters (QNH-corrected)
        'H(ft)',  # Height in feet (QNH-corrected)
        'RHO',  # Slant range (NM) - CAT048 only
        'THETA',  # Azimuth angle (degrees) - CAT048 only
        'Mode3/A',  # Mode 3/A code (octal)

        # Aircraft identification
        'FL',  # Flight Level
        'TA',  # Target Address (24-bit ICAO address, hex)
        'TI',  # Target Identification (callsign)
        'BP',  # Barometric Pressure (hPa)
        'ModeS',  # BDS registers present

        # BDS 5.0 - Track and Turn Report
        'RA',  # Roll Angle (deg)
        'TTA',  # True Track Angle (deg)
        'GS(kt)',  # Ground Speed (kt)
        'TAR',  # Track Angle Rate (deg/s)
        'TAS',  # True Airspeed (kt)

        # BDS 6.0 - Heading and Speed Report
        'HDG',  # Heading (deg) - radar-measured
        'MG_HDG',  # Magnetic Heading (deg) - aircraft-reported
        'IAS',  # Indicated Airspeed (kt)
        'MACH',  # Mach Number
        'BAR',  # Barometric Altitude Rate (ft/min)
        'IVV',  # Inertial Vertical Velocity (ft/min)

        # Track/Status
        'TN',  # Track Number

        # Detection/Quality fields
        'TYP',  # Detection type (PSR/SSR/Mode S/CMB)
        'SIM',  # Simulated target indicator (0/1)
        'RDP',  # RDP Chain (1/2)
        'SPI',  # Special Position Identification (0/1)
        'RAB',  # Report from field monitor (0/1)

        # CAT021-specific fields
        'ATP',  # Address Type
        'ARC',  # Altitude Reporting Capability
        'RC',  # Range Check
        'DCR',  # Differential Correction
        'GBS',  # Ground Bit Set
        'TST',  # Test Target

        'STAT_code',  # Status code - COM/ACAS
        'STAT',  # Status description - COM/ACAS
    ]

    @staticmethod
    def records_to_dataframe(records: List[Record], apply_qnh: bool = True) -> pd.DataFrame:
        """
        Convert a mixed list of Record objects (any category) to a unified pandas DataFrame.
        Optionally applies QNH correction during export.

        Memory optimizations:
        - Builds DataFrame from list of dicts (standard approach)
        - Immediately applies dtype downcasting to reduce memory footprint
        - Avoids unnecessary copies during construction

        Args:
            records: List of Record objects from any ASTERIX category
            apply_qnh: Whether to apply QNH correction (default: True)

        Returns:
            pd.DataFrame with unified schema and optimized dtypes
        """
        rows = []

        for record in records:
            row = {col: None for col in AsterixExporter.ALL_COLUMNS}
            row['CAT'] = record.category.value

            if record.category == Category.CAT021:
                AsterixExporter._process_cat021(record, row)
            elif record.category == Category.CAT048:
                AsterixExporter._process_cat048(record, row)

            rows.append(row)

        df = pd.DataFrame(rows, columns=AsterixExporter.ALL_COLUMNS)

        # PRIORITY 2: Apply dtype downcasting immediately after DataFrame creation
        df = AsterixExporter._downcast_dtypes(df)

        # Sort by time and aircraft address (use inplace to reduce temporaries)
        if 'Time_sec' in df.columns and 'TA' in df.columns:
            df.sort_values(['Time_sec', 'TA'], na_position='last', inplace=True)
            df.reset_index(drop=True, inplace=True)

        # Apply QNH correction if requested
        if apply_qnh:
            df = AsterixExporter._apply_qnh_correction(df)

        return df

    @staticmethod
    def _downcast_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """
        Args:
            df: DataFrame with default dtypes (mostly int64/float64/object)

        Returns:
            DataFrame with optimized dtypes matching CSV format
        """
        if df is None or df.empty:
            return df

        # Integer columns - codes and flags (0/1 values)
        # These include: SAC, SIC, CAT, RDP, TYP, SIM, SPI, RAB, TST, ATP, ARC, RC, DCR, GBS
        int_cols = [
            'CAT', 'SAC', 'SIC', 'RDP', 'TYP', 'SIM', 'SPI', 'RAB', 'TST', 'STAT_code',
            'ATP', 'ARC', 'RC', 'DCR', 'GBS', 'TN', 'TAS', 'IAS', 'BAR', 'IVV'
        ]
        for col in int_cols:
            if col in df.columns:
                try:
                    # Convert to numeric, then to int64 (preserves None/NaN as NA)
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                except (ValueError, TypeError):
                    pass

        # Floating-point measurements - downcast float64 to float32
        # These include: coordinates, speeds, altitudes, rates, etc.
        float_cols = [
            'LAT', 'LON', 'RHO', 'THETA', 'H(m)', 'H(ft)', 'H_WGS84',
            'GS(kt)', 'HDG', 'MG_HDG', 'TTA', 'RA', 'TAR', 'MACH',
            'BP', 'FL', 'Time_sec'
        ]
        for col in float_cols:
            if col in df.columns:
                try:
                    # Convert to numeric first, then float32
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('float32')
                except (ValueError, TypeError):
                    pass

        # Categorical strings for high-cardinality repeated values
        # Target Address (TA) and Target Identification (TI) repeat frequently
        if 'TA' in df.columns and df['TA'].notna().any():
            try:
                df['TA'] = df['TA'].astype('category')
            except (ValueError, TypeError):
                pass

        if 'TI' in df.columns and df['TI'].notna().any():
            try:
                df['TI'] = df['TI'].astype('category')
            except (ValueError, TypeError):
                pass

        # Keep all other columns as object/string
        # This includes: Time, Mode3/A, ModeS, STAT, STAT_code
        # These export correctly as strings in CSV

        return df

    @staticmethod
    def _apply_qnh_correction(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply QNH correction using aircraft address for state tracking.

        Only populates H(ft) and H(m) for records below transition altitude with valid QNH.
        Uses per-aircraft state tracking to maintain QNH setting across multiple reports.

        PRIORITY 1: No copy() - adds columns in place to avoid memory doubling.

        Args:
            df: DataFrame with FL, TA, and BP columns

        Returns:
            DataFrame with H(ft) and H(m) populated where applicable
        """
        if 'FL' not in df.columns or 'TA' not in df.columns:
            return df

        corrector = QNHCorrector()
        alt_ft_list = []
        alt_m_list = []

        for _, row in df.iterrows():
            ta = row.get('TA')
            fl = row.get('FL')
            bp = row.get('BP')

            corrected_alt_ft = corrector.correct(ta, fl, bp)

            if corrected_alt_ft is not None:
                alt_ft_list.append(corrected_alt_ft)
                alt_m_list.append(corrected_alt_ft * 0.3048)
            else:
                alt_ft_list.append(None)
                alt_m_list.append(None)

        # Add columns directly without copying - only H(ft) and H(m) are added
        df['H(ft)'] = alt_ft_list
        df['H(m)'] = alt_m_list

        return df

    @staticmethod
    def _process_cat021(record: Record, row: dict) -> None:
        """
        Process CAT021-specific items and populate row dictionary.

        CAT021 provides ADS-B data with high-precision WGS-84 coordinates.
        """
        for item in record.items:
            item_type = item.item_type
            value = item.value

            if item_type == CAT021ItemType.DATA_SOURCE_IDENTIFICATION:
                row['SAC'] = value.get('SAC')
                row['SIC'] = value.get('SIC')

            elif item_type == CAT021ItemType.TARGET_REPORT_DESCRIPTOR:
                row['ATP'] = value.get('ATP')
                row['ARC'] = value.get('ARC')
                row['RC'] = value.get('RC')
                row['RAB'] = value.get('RAB')
                row['DCR'] = value.get('DCR')
                row['GBS'] = value.get('GBS')
                row['SIM'] = value.get('SIM')
                row['TST'] = value.get('TST')

            elif item_type == CAT021ItemType.POSITION_WGS84_HIGH_RES:
                row['LAT'] = value.get('latitude')
                row['LON'] = value.get('longitude')

            elif item_type == CAT021ItemType.TARGET_ADDRESS:
                row['TA'] = value.get('target_address_hex')

            elif item_type == CAT021ItemType.TIME_MESSAGE_RECEPTION_POSITION:
                row['Time'] = value.get('formatted')
                row['Time_sec'] = value.get('total_seconds')

            elif item_type == CAT021ItemType.MODE_3A_CODE:
                row['Mode3/A'] = value.get('mode_3a_code')

            elif item_type == CAT021ItemType.FLIGHT_LEVEL:
                row['FL'] = value.get('flight_level')

            elif item_type == CAT021ItemType.TARGET_IDENTIFICATION:
                row['TI'] = value.get('callsign')

            elif item_type == CAT021ItemType.RESERVED_EXPANSION_FIELD:
                row['BP'] = value.get('BP')

    @staticmethod
    def _process_cat048(record: Record, row: dict) -> None:
        """
        Process CAT048-specific items and populate row dictionary.

        CAT048 provides radar data with polar coordinates and Mode S BDS registers.
        Implements precedence for speed/heading: radar measurements take priority over BDS.
        """
        bds_present = []

        for item in record.items:
            item_type = item.item_type
            value = item.value

            if item_type == CAT048ItemType.DATA_SOURCE_IDENTIFIER:
                row['SAC'] = value.get('SAC')
                row['SIC'] = value.get('SIC')

            elif item_type == CAT048ItemType.TIME_OF_DAY:
                row['Time'] = value.get('formatted')
                row['Time_sec'] = value.get('total_seconds')

            elif item_type == CAT048ItemType.MEASURED_POSITION_POLAR:
                row['RHO'] = value.get('RHO_nm')
                row['THETA'] = value.get('THETA_degrees')
                row['LAT'] = value.get('latitude')
                row['LON'] = value.get('longitude')
                row['H_WGS84'] = value.get('height_m')

            elif item_type == CAT048ItemType.MODE_3A_CODE:
                row['Mode3/A'] = value.get('Mode3/A')

            elif item_type == CAT048ItemType.FLIGHT_LEVEL:
                row['FL'] = value.get('FL')

            elif item_type == CAT048ItemType.AIRCRAFT_ADDRESS:
                row['TA'] = value.get('aircraft_address_hex')

            elif item_type == CAT048ItemType.AIRCRAFT_IDENTIFICATION:
                row['TI'] = value.get('TI')

            elif item_type == CAT048ItemType.TRACK_NUMBER:
                row['TN'] = value.get('TN')

            elif item_type == CAT048ItemType.TRACK_VELOCITY_POLAR:
                row['GS(kt)'] = value.get('GS_kt')
                row['HDG'] = value.get('HDG_degrees')

            elif item_type == CAT048ItemType.COMMUNICATIONS_ACAS:
                row['STAT'] = value.get('STAT_description')
                row['STAT_code'] = value.get('STAT')

            elif item_type == CAT048ItemType.TARGET_REPORT_DESCRIPTOR:
                row['TYP'] = value.get('TYP')
                row['SIM'] = value.get('SIM')
                row['RDP'] = value.get('RDP')
                row['SPI'] = value.get('SPI')
                row['RAB'] = value.get('RAB')

            elif item_type == CAT048ItemType.MODE_S_MB_DATA:
                bds_registers = value.get('bds_registers', [])

                for bds_reg in bds_registers:
                    bds_code = bds_reg.get('bds_code')
                    if bds_code:
                        bds_formatted = f"BDS {bds_code[0]}.{bds_code[1]}"
                        if bds_formatted not in bds_present:
                            bds_present.append(bds_formatted)

                    if 'BP_mb' in bds_reg:
                        row['BP'] = bds_reg['BP_mb']

                    if 'RA_deg' in bds_reg:
                        row['RA'] = bds_reg['RA_deg']

                    if 'TTA_deg' in bds_reg:
                        row['TTA'] = bds_reg['TTA_deg']

                    if 'GS_kt' in bds_reg:
                        if row.get('GS(kt)') is None:
                            row['GS(kt)'] = bds_reg['GS_kt']

                    if 'TAR_deg_s' in bds_reg:
                        row['TAR'] = bds_reg['TAR_deg_s']

                    if 'TAS_kt' in bds_reg:
                        row['TAS'] = bds_reg['TAS_kt']

                    if 'MG_HDG_deg' in bds_reg:
                        row['MG_HDG'] = bds_reg['MG_HDG_deg']

                    if 'IAS_kt' in bds_reg:
                        row['IAS'] = bds_reg['IAS_kt']

                    if 'MACH' in bds_reg:
                        row['MACH'] = bds_reg['MACH']

                    if 'BAR_RATE_ft_min' in bds_reg:
                        row['BAR'] = bds_reg['BAR_RATE_ft_min']

                    if 'IVV_ft_min' in bds_reg:
                        row['IVV'] = bds_reg['IVV_ft_min']

        if bds_present:
            row['ModeS'] = ' '.join(bds_present)

    @staticmethod
    def export_to_csv(df: pd.DataFrame, output_path: str, na_rep: str = 'N/A') -> None:
        """
        Export DataFrame to CSV file.

        Args:
            df: DataFrame to export
            output_path: Output file path
            na_rep: String to represent missing values (default: 'N/A')
        """
        df.to_csv(output_path, index=False, na_rep=na_rep)
        print(f"✅ Exported {len(df):,} records to {output_path}")

    @staticmethod
    def get_column_info() -> dict:
        """
        Get detailed information about all columns.

        Returns:
            Dictionary mapping column names to descriptions
        """
        return {
            'CAT': 'ASTERIX Category (21=ADS-B, 48=Radar)',
            'SAC': 'System Area Code',
            'SIC': 'System Identification Code',
            'Time': 'Time of day (HH:MM:SS.mmm)',
            'Time_sec': 'Time in seconds from midnight',
            'LAT': 'Latitude (degrees)',
            'LON': 'Longitude (degrees)',
            'H(m)': 'QNH-corrected height (meters)',
            'H(ft)': 'QNH-corrected height (feet)',
            'RHO': 'Slant range (nautical miles)',
            'THETA': 'Azimuth angle (degrees, 0°=North)',
            'H_WGS84': 'WGS-84 ellipsoidal height (meters)',
            'Mode3/A': 'Mode 3/A code (octal)',
            'FL': 'Flight Level (x100 ft)',
            'TA': 'Target Address (24-bit ICAO, hex)',
            'TI': 'Target Identification (callsign)',
            'TN': 'Track Number',
            'ModeS': 'BDS registers present',
            'BP': 'Barometric Pressure Setting (hPa)',
            'GS(kt)': 'Ground Speed (knots, radar or BDS 5.0)',
            'HDG': 'Heading (degrees, radar-measured)',
            'MG_HDG': 'Magnetic Heading (degrees, BDS 6.0)',
            'TTA': 'True Track Angle (degrees, BDS 5.0)',
            'RA': 'Roll Angle (degrees, BDS 5.0)',
            'TAR': 'Track Angle Rate (deg/s, BDS 5.0)',
            'TAS': 'True Airspeed (knots, BDS 5.0)',
            'IAS': 'Indicated Airspeed (knots, BDS 6.0)',
            'MACH': 'Mach Number (BDS 6.0)',
            'BAR': 'Barometric Altitude Rate (ft/min, BDS 6.0)',
            'IVV': 'Inertial Vertical Velocity (ft/min, BDS 6.0)',
            'STAT': 'Communications/ACAS status description',
            'STAT_code': 'Communications/ACAS status code',
            'TYP': 'Detection type (PSR/SSR/Mode S/CMB)',
            'SIM': 'Simulated target indicator (0/1)',
            'RDP': 'RDP Chain (1/2)',
            'SPI': 'Special Position Identification (0/1)',
            'RAB': 'Report from field monitor (0/1)',
            'ATP': 'Address Type (CAT021)',
            'ARC': 'Altitude Reporting Capability (CAT021)',
            'RC': 'Range Check (CAT021)',
            'DCR': 'Differential Correction (CAT021)',
            'GBS': 'Ground Bit Set (CAT021)',
            'TST': 'Test Target (CAT021)',
        }
