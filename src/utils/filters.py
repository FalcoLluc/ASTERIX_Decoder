import pandas as pd


class Cat021AnalysisHelper:
    """Helper methods for filtering and analyzing CAT021 data"""

    @staticmethod
    def filter_airborne(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for airborne aircraft (GBS=0)"""
        if 'GBS' not in df.columns:
            return df
        return df[df['GBS'] == 0]

    @staticmethod
    def filter_on_ground(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for aircraft on ground (GBS=1)"""
        if 'GBS' not in df.columns:
            return df
        return df[df['GBS'] == 1]

    @staticmethod
    def filter_by_altitude(df: pd.DataFrame, min_fl: float = None, max_fl: float = None) -> pd.DataFrame:
        """Filter by flight level range"""
        if 'Flight_Level' not in df.columns:
            return df
        result = df.copy()
        if min_fl is not None:
            result = result[result['Flight_Level'] >= min_fl]
        if max_fl is not None:
            result = result[result['Flight_Level'] <= max_fl]
        return result

    @staticmethod
    def filter_by_callsign(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
        """Filter by callsign pattern (e.g., 'RYR' for Ryanair)"""
        if 'Target_identification' not in df.columns:
            return df
        return df[df['Target_identification'].str.contains(pattern, na=False, case=False)]

    @staticmethod
    def filter_by_position(df: pd.DataFrame,
                           min_lat: float = None, max_lat: float = None,
                           min_lon: float = None, max_lon: float = None) -> pd.DataFrame:
        """Filter by geographic position"""
        if 'Latitud' not in df.columns or 'Longitud' not in df.columns:
            return df
        result = df.copy()
        if min_lat is not None:
            result = result[result['Latitud'] >= min_lat]
        if max_lat is not None:
            result = result[result['Latitud'] <= max_lat]
        if min_lon is not None:
            result = result[result['Longitud'] >= min_lon]
        if max_lon is not None:
            result = result[result['Longitud'] <= max_lon]
        return result

    @staticmethod
    def filter_simulated(df: pd.DataFrame, include_sim: bool = False) -> pd.DataFrame:
        """Filter simulated targets"""
        if 'SIM' not in df.columns:
            return df
        if include_sim:
            return df
        return df[df['SIM'] == 0]

    @staticmethod
    def filter_test_targets(df: pd.DataFrame, include_test: bool = False) -> pd.DataFrame:
        """Filter test targets"""
        if 'TST' not in df.columns:
            return df
        if include_test:
            return df
        return df[df['TST'] == 0]

    @staticmethod
    def filter_by_address_type(df: pd.DataFrame, atp: int) -> pd.DataFrame:
        """Filter by address type"""
        if 'ATP' not in df.columns:
            return df
        return df[df['ATP'] == atp]

    @staticmethod
    def get_statistics(df: pd.DataFrame) -> dict:
        """Get basic statistics for the dataset"""
        return {
            'total_records': len(df),
            'unique_aircraft': df['Target_address'].nunique() if 'Target_address' in df.columns else 0,
            'unique_callsigns': df['Target_identification'].nunique() if 'Target_identification' in df.columns else 0,
            'airborne_count': len(Cat021AnalysisHelper.filter_airborne(df)) if 'GBS' in df.columns else None,
            'ground_count': len(Cat021AnalysisHelper.filter_on_ground(df)) if 'GBS' in df.columns else None,
            'avg_altitude_ft': df['h_ft'].mean() if 'h_ft' in df.columns else None,
            'avg_flight_level': df['Flight_Level'].mean() if 'Flight_Level' in df.columns else None,
            'altitude_range': (df['Flight_Level'].min(), df['Flight_Level'].max()) if 'Flight_Level' in df.columns else None,
            'lat_range': (df['Latitud'].min(), df['Latitud'].max()) if 'Latitud' in df.columns else None,
            'lon_range': (df['Longitud'].min(), df['Longitud'].max()) if 'Longitud' in df.columns else None,
            'simulated_count': (df['SIM'] == 1).sum() if 'SIM' in df.columns else None,
            'test_target_count': (df['TST'] == 1).sum() if 'TST' in df.columns else None,
            'avg_barometric_pressure': df['BP'].mean() if 'BP' in df.columns else None,
        }

    @staticmethod
    def get_aircraft_trajectory(df: pd.DataFrame, target_address: str) -> pd.DataFrame:
        """Get all records for a specific aircraft"""
        if 'Target_address' not in df.columns:
            return pd.DataFrame()
        trajectory = df[df['Target_address'] == target_address].copy()
        if 'Time' in trajectory.columns:
            trajectory = trajectory.sort_values('Time')
        return trajectory

    @staticmethod
    def get_top_aircraft_by_records(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        """Get top N aircraft by number of records"""
        if 'Target_address' not in df.columns:
            return pd.DataFrame()
        aircraft_counts = df.groupby('Target_address').agg({
            'Target_identification': 'first',
            'Target_address': 'count'
        }).rename(columns={'Target_address': 'record_count'})

        aircraft_counts = aircraft_counts.sort_values('record_count', ascending=False)
        return aircraft_counts.head(n).reset_index()


class Cat048AnalysisHelper:
    """Helper methods for filtering and analyzing CAT048 data"""

    @staticmethod
    def filter_airborne(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for airborne aircraft (STAT230 = 0 or 2)"""
        if 'STAT230' not in df.columns:
            return df
        return df[df['STAT230'].isin([0, 2])]

    @staticmethod
    def filter_on_ground(df: pd.DataFrame) -> pd.DataFrame:
        """Filter for aircraft on ground (STAT230 = 1 or 3)"""
        if 'STAT230' not in df.columns:
            return df
        return df[df['STAT230'].isin([1, 3])]

    @staticmethod
    def filter_by_altitude(df: pd.DataFrame, min_fl: float = None, max_fl: float = None) -> pd.DataFrame:
        """Filter by flight level range"""
        if 'Flight_Level' not in df.columns:
            return df
        result = df.copy()
        if min_fl is not None:
            result = result[result['Flight_Level'] >= min_fl]
        if max_fl is not None:
            result = result[result['Flight_Level'] <= max_fl]
        return result

    @staticmethod
    def filter_by_callsign(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
        """Filter by callsign pattern (e.g., 'RYR' for Ryanair)"""
        if 'Target_identification' not in df.columns:
            return df
        return df[df['Target_identification'].str.contains(pattern, na=False, case=False)]

    @staticmethod
    def filter_by_speed(df: pd.DataFrame, min_speed: float = None, max_speed: float = None) -> pd.DataFrame:
        """Filter by ground speed (BDS 5.0)"""
        if 'GS' not in df.columns:
            return df
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
            'unique_aircraft': df['Target_address'].nunique() if 'Target_address' in df.columns else 0,
            'airborne_count': len(Cat048AnalysisHelper.filter_airborne(df)) if 'STAT230' in df.columns else 0,
            'ground_count': len(Cat048AnalysisHelper.filter_on_ground(df)) if 'STAT230' in df.columns else 0,
            'avg_altitude_ft': (df['Flight_Level'].mean() * 100) if 'Flight_Level' in df.columns else None,
            'avg_ground_speed_kt': df['GS'].mean() if 'GS' in df.columns else None,
            'altitude_range': (df['Flight_Level'].min(), df['Flight_Level'].max()) if 'Flight_Level' in df.columns else None,
        }
