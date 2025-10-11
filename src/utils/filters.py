import pandas as pd

class Cat021AnalysisHelper:

    @staticmethod
    def filter_airborne(df: pd.DataFrame) -> pd.DataFrame:
        return df[df['GBS'] == 0]

    @staticmethod
    def filter_on_ground(df: pd.DataFrame) -> pd.DataFrame:
        return df[df['GBS'] == 1]

    @staticmethod
    def filter_by_altitude(df: pd.DataFrame, min_fl: float = None, max_fl: float = None) -> pd.DataFrame:
        result = df.copy()
        if min_fl is not None:
            result = result[result['FL'] >= min_fl]
        if max_fl is not None:
            result = result[result['FL'] <= max_fl]
        return result

    @staticmethod
    def filter_by_callsign(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
        return df[df['TI'].str.contains(pattern, na=False, case=False)]

    @staticmethod
    def filter_by_position(df: pd.DataFrame,
                           min_lat: float = None, max_lat: float = None,
                           min_lon: float = None, max_lon: float = None) -> pd.DataFrame:
        result = df.copy()
        if min_lat is not None:
            result = result[result['LAT'] >= min_lat]
        if max_lat is not None:
            result = result[result['LAT'] <= max_lat]
        if min_lon is not None:
            result = result[result['LON'] >= min_lon]
        if max_lon is not None:
            result = result[result['LON'] <= max_lon]
        return result

    @staticmethod
    def filter_simulated(df: pd.DataFrame, include_sim: bool = False) -> pd.DataFrame:
        if include_sim:
            return df
        return df[df['SIM'] == 0]

    @staticmethod
    def filter_test_targets(df: pd.DataFrame, include_test: bool = False) -> pd.DataFrame:
        if include_test:
            return df
        return df[df['TST'] == 0]

    @staticmethod
    def filter_by_address_type(df: pd.DataFrame, atp: int) -> pd.DataFrame:
        return df[df['ATP'] == atp]

    @staticmethod
    def get_statistics(df: pd.DataFrame) -> dict:
        return {
            'total_records': len(df),
            'unique_aircraft': df['TA'].nunique() if 'TA' in df.columns else 0,
            'unique_callsigns': df['TI'].nunique() if 'TI' in df.columns else 0,
            'airborne_count': len(Cat021AnalysisHelper.filter_airborne(df)) if 'GBS' in df.columns else None,
            'ground_count': len(Cat021AnalysisHelper.filter_on_ground(df)) if 'GBS' in df.columns else None,
            'avg_altitude_ft': df['ALT_ft'].mean() if 'ALT_ft' in df.columns else None,
            'avg_flight_level': df['FL'].mean() if 'FL' in df.columns else None,
            'altitude_range': (df['FL'].min(), df['FL'].max()) if 'FL' in df.columns else None,
            'lat_range': (df['LAT'].min(), df['LAT'].max()) if 'LAT' in df.columns else None,
            'lon_range': (df['LON'].min(), df['LON'].max()) if 'LON' in df.columns else None,
            'simulated_count': (df['SIM'] == 1).sum() if 'SIM' in df.columns else None,
            'test_target_count': (df['TST'] == 1).sum() if 'TST' in df.columns else None,
            'avg_barometric_pressure': df['BP'].mean() if 'BP' in df.columns else None,
        }

    @staticmethod
    def get_aircraft_trajectory(df: pd.DataFrame, target_address: str) -> pd.DataFrame:
        trajectory = df[df['TA'] == target_address].copy()
        if 'Time' in trajectory.columns:
            trajectory = trajectory.sort_values('Time')
        return trajectory

    @staticmethod
    def get_top_aircraft_by_records(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        aircraft_counts = df.groupby('TA').agg({
            'TI': 'first',
            'TA': 'count'
        }).rename(columns={'TA': 'record_count'})

        aircraft_counts = aircraft_counts.sort_values('record_count', ascending=False)
        return aircraft_counts.head(n).reset_index()

class Cat048AnalysisHelper:
    """Helper methods for filtering and analyzing CAT048 data"""

    @staticmethod
    def filter_airborne(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for airborne aircraft (STAT = 0 or 2)"""
        return df[df['STAT'].isin([0, 2])]

    @staticmethod
    def filter_on_ground(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for aircraft on ground (STAT = 1 or 3)"""
        return df[df['STAT'].isin([1, 3])]

    @staticmethod
    def filter_by_altitude(df: pd.DataFrame, min_fl: float = None, max_fl: float = None) -> pd.DataFrame:
        """Filter by flight level range"""
        result = df.copy()
        if min_fl is not None:
            result = result[result['FL'] >= min_fl]
        if max_fl is not None:
            result = result[result['FL'] <= max_fl]
        return result

    @staticmethod
    def filter_by_callsign(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
        """Filter by callsign pattern (e.g., 'RYR' for Ryanair)"""
        return df[df['TI'].str.contains(pattern, na=False, case=False)]

    @staticmethod
    def filter_by_speed(df: pd.DataFrame, min_speed: float = None, max_speed: float = None) -> pd.DataFrame:
        """Filter by ground speed"""
        result = df.copy()
        if min_speed is not None:
            result = result[result['GS'] >= min_speed]
        if max_speed is not None:
            result = result[result['GS'] <= max_speed]
        return result

    @staticmethod
    def get_statistics(df: pd.DataFrame) -> dict:
        """Get basic statistics for the dataset"""
        return {
            'total_records': len(df),
            'unique_aircraft': df['TA'].nunique(),
            'airborne_count': len(Cat048AnalysisHelper.filter_airborne(df)),
            'ground_count': len(Cat048AnalysisHelper.filter_on_ground(df)),
            'avg_altitude_ft': df['FL'].mean() * 100 if 'FL' in df.columns else None,
            'avg_ground_speed_kt': df['GS'].mean() if 'GS' in df.columns else None,
            'altitude_range': (df['FL'].min(), df['FL'].max()) if 'FL' in df.columns else None,
        }
