import pandas as pd
from typing import Optional, List


class AsterixFilter:
    """
    Unified filtering class for all ASTERIX categories.
    Works with pandas DataFrames containing any category data.
    Filters gracefully handle missing columns by returning the input unchanged.
    """
    LAT_MIN = 40.99
    LAT_MAX = 41.7
    LON_MIN = 1.5
    LON_MAX = 2.6

    @staticmethod
    def filter_by_geographic_bounds(df: pd.DataFrame,
                                    min_lat: float = LAT_MIN,
                                    max_lat: float = LAT_MAX,
                                    min_lon: float = LON_MIN,
                                    max_lon: float = LON_MAX) -> pd.DataFrame:
        """Filter to geographic bounding box"""
        if 'LAT' not in df.columns or 'LON' not in df.columns:
            return df

        mask = (
                (df['LAT'] >= min_lat) &
                (df['LAT'] <= max_lat) &
                (df['LON'] >= min_lon) &
                (df['LON'] <= max_lon)
        )
        return df[mask].reset_index(drop=True)

    @staticmethod
    def filter_airborne(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for airborne aircraft using any available indicator."""
        if 'STAT_code' not in df.columns and 'GBS' not in df.columns:
            return df

        mask = pd.Series(False, index=df.index)
        if 'STAT_code' in df.columns:
            mask = mask | df['STAT_code'].isin([0, 2])
        if 'GBS' in df.columns:
            mask = mask | (df['GBS'] == 0)

        return df[mask].reset_index(drop=True)

    @staticmethod
    def filter_on_ground(df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter for aircraft on ground using any available indicator.
        CAT021: GBS=1 (on ground)
        CAT048: STAT_code in [1, 3] (on ground)
        """
        if 'STAT_code' not in df.columns and 'GBS' not in df.columns:
            return df

        mask = pd.Series(False, index=df.index)
        if 'STAT_code' in df.columns:
            mask = mask | df['STAT_code'].isin([1, 3])
        if 'GBS' in df.columns:
            mask = mask | (df['GBS'] == 1)

        return df[mask].reset_index(drop=True)

    @staticmethod
    def filter_by_altitude(df: pd.DataFrame,
                           min_fl: Optional[float] = None,
                           max_fl: Optional[float] = None) -> pd.DataFrame:
        """Filter by flight level range"""
        if 'FL' not in df.columns:
            return df

        result = df.copy()
        if min_fl is not None:
            result = result[result['FL'] >= min_fl]
        if max_fl is not None:
            result = result[result['FL'] <= max_fl]

        return result.reset_index(drop=True)

    @staticmethod
    def filter_by_callsign(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
        """Filter by callsign pattern (e.g., 'RYR' for Ryanair)"""
        if 'TI' not in df.columns:
            return df

        return df[df['TI'].str.contains(pattern, na=False, case=False)].reset_index(drop=True)

    @staticmethod
    def filter_simulated(df: pd.DataFrame, include_sim: bool = False) -> pd.DataFrame:
        """Filter simulated targets (CAT021 only)"""
        if 'SIM' not in df.columns:
            return df

        if include_sim:
            return df

        return df[df['SIM'] == 0].reset_index(drop=True)

    @staticmethod
    def filter_test_targets(df: pd.DataFrame, include_test: bool = False) -> pd.DataFrame:
        """Filter test targets (CAT021 only)"""
        if 'TST' not in df.columns:
            return df

        if include_test:
            return df

        return df[df['TST'] == 0].reset_index(drop=True)

    @staticmethod
    def filter_white_noise(df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter white noise by detection type (CAT048 TYP field only).
        Keeps only Mode S detections for CAT048 records.
        CAT021 records are not affected by this filter.

        Detection types (from CAT048 I048020):
        - 000: No detection (should not occur)
        - 001: Single PSR detection (white noise - discard)
        - 010: Single SSR detection (discard)
        - 011: SSR + PSR (discard)
        - 100: Single Mode S All-Call (keep)
        - 101: Single Mode S Roll-Call (keep)
        - 110: Mode S All-Call + PSR (keep)
        - 111: Mode S Roll-Call + PSR (keep)

        Args:
            df: DataFrame to filter (can contain both CAT021 and CAT048)

        Returns:
            Filtered DataFrame with white noise removed from CAT048 records only
        """
        if 'TYP' not in df.columns or 'CAT' not in df.columns:
            return df

        # Separate CAT021 and CAT048 records
        cat021_mask = df['CAT'] == 21
        cat048_mask = df['CAT'] == 48

        # Keep all CAT021 records unchanged
        cat021_records = df[cat021_mask]

        # Filter CAT048 records: keep only Mode S detections (TYP = 4, 5, 6, 7)
        cat048_records = df[cat048_mask]
        mode_s_mask = cat048_records['TYP'].isin([4, 5, 6, 7])
        cat048_filtered = cat048_records[mode_s_mask]

        # Combine CAT021 (all) and CAT048 (filtered) records
        result = pd.concat([cat021_records, cat048_filtered], ignore_index=True)

        # Sort by original order (Time and TA if available)
        if 'Time' in result.columns and 'TA' in result.columns:
            result = result.sort_values(['Time', 'TA'], na_position='last')

        return result.reset_index(drop=True)

    @staticmethod
    def filter_by_speed(df: pd.DataFrame,
                        min_speed: Optional[float] = None,
                        max_speed: Optional[float] = None) -> pd.DataFrame:
        """Filter by ground speed"""
        # Try GS field first (BDS 5.0)
        speed_col = None
        if 'GS' in df.columns:
            speed_col = 'GS'
        elif 'GS(kt)' in df.columns:
            speed_col = 'GS(kt)'

        if speed_col is None:
            return df

        result = df.copy()
        if min_speed is not None:
            result = result[result[speed_col] >= min_speed]
        if max_speed is not None:
            result = result[result[speed_col] <= max_speed]

        return result.reset_index(drop=True)

    @staticmethod
    def filter_by_aircraft_addresses(df: pd.DataFrame, addresses: List[str]) -> pd.DataFrame:
        """Filter by specific aircraft addresses"""
        if 'TA' not in df.columns:
            return df

        return df[df['TA'].isin(addresses)].reset_index(drop=True)

    @staticmethod
    def get_statistics(df: pd.DataFrame) -> dict:
        """Get basic statistics for the dataset (works with any category)"""
        stats = {
            'total_records': len(df),
            'unique_aircraft': df['TA'].nunique() if 'TA' in df.columns else 0,
            'unique_callsigns': df['TI'].nunique() if 'TI' in df.columns else 0,
        }

        # Airborne/ground counts
        if 'GBS' in df.columns:
            stats['airborne_count'] = (df['GBS'] == 0).sum()
            stats['ground_count'] = (df['GBS'] == 1).sum()
        elif 'STAT' in df.columns:
            stats['airborne_count'] = df['STAT'].isin([0, 2]).sum()
            stats['ground_count'] = df['STAT'].isin([1, 3]).sum()

        # Altitude statistics
        if 'H(ft)' in df.columns:
            stats['avg_altitude_ft'] = df['H(ft)'].mean()
            stats['altitude_range_ft'] = (df['H(ft)'].min(), df['H(ft)'].max())

        if 'FL' in df.columns:
            stats['avg_flight_level'] = df['FL'].mean()
            stats['fl_range'] = (df['FL'].min(), df['FL'].max())

        # Position statistics
        if 'LAT' in df.columns and 'LON' in df.columns:
            stats['lat_range'] = (df['LAT'].min(), df['LAT'].max())
            stats['lon_range'] = (df['LON'].min(), df['LON'].max())

        # CAT021 specific
        if 'SIM' in df.columns:
            stats['simulated_count'] = (df['SIM'] == 1).sum()
        if 'TST' in df.columns:
            stats['test_target_count'] = (df['TST'] == 1).sum()
        if 'BP' in df.columns:
            stats['avg_barometric_pressure'] = df['BP'].mean()

        return stats
