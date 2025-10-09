import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT021ItemType


class Cat021CSVExporter:

    @staticmethod
    def records_to_dataframe(records: List[Record]) -> pd.DataFrame:
        rows = []

        for record in records:
            row = {
                'CAT': record.category.value,
                'SAC': None,
                'SIC': None,
            }

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
                    row['Time'] = value.get('total_seconds')

                elif item_type == CAT021ItemType.MODE_3A_CODE:
                    row['Mode3/A'] = value.get('mode_3a_code')

                elif item_type == CAT021ItemType.FLIGHT_LEVEL:
                    row['FL'] = value.get('flight_level')
                    row['ALT_ft'] = value.get('altitude_feet')

                elif item_type == CAT021ItemType.TARGET_IDENTIFICATION:
                    row['TI'] = value.get('callsign')

                elif item_type == CAT021ItemType.RESERVED_EXPANSION_FIELD:
                    row['BPS'] = value.get('BPS')

            rows.append(row)

        df = pd.DataFrame(rows)

        column_order = [
            'CAT', 'SAC', 'SIC', 'Time',
            'ATP', 'ARC', 'RC', 'RAB', 'DCR', 'GBS', 'SIM', 'TST',
            'LAT', 'LON',
            'TA',
            'Mode3/A',
            'FL', 'ALT_ft',
            'TI',
            'BPS'
        ]

        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]

        return df

    @staticmethod
    def export_to_csv(records: List[Record], output_path: str, apply_filters: bool = True):
        """
        Exporta registros a CSV aplicando filtros obligatorios del proyecto

        Args:
            records: Lista de registros decodificados
            output_path: Ruta del archivo CSV
            apply_filters: Si True, aplica filtros geográficos, ground y QNH
        """
        from src.utils.preprocessor import AsterixPreprocessor

        initial_count = len(records)

        if apply_filters:
            print(f"  🔄 Aplicando filtros obligatorios...")
            print(f"     Registros iniciales: {initial_count:,}")

            records = AsterixPreprocessor.filter_records_cat021(records)

            print(f"     Después de filtros: {len(records):,}")
            print(f"     Descartados: {initial_count - len(records):,}")

        df = Cat021CSVExporter.records_to_dataframe(records)

        if apply_filters:
            print(f"  🔄 Aplicando corrección QNH...")
            if 'BPS' in df.columns and df['BPS'].notna().any():
                df = AsterixPreprocessor.apply_qnh_with_bp(df)
            else:
                df = AsterixPreprocessor.apply_qnh_correction(df)

        df.to_csv(output_path, index=False, na_rep='N/A')

        return df


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
            'avg_barometric_pressure': df['BPS'].mean() if 'BPS' in df.columns else None,
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
