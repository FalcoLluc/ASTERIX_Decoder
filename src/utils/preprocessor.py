import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT021ItemType, CAT048ItemType

class AsterixPreprocessor:
    GEOGRAPHIC_BOUNDS = {
        'lat_min': 40.9,
        'lat_max': 41.7,
        'lon_min': 1.5,
        'lon_max': 2.6
    }

    QNH_STANDARD = 1013.25
    TRANSITION_ALTITUDE = 6000

    @staticmethod
    def filter_records_cat021(records: List[Record]) -> List[Record]:
        """Filtra registros CAT021: área geográfica + eliminar ground"""
        filtered_records = []

        for record in records:
            has_valid_position = False
            is_ground = False
            lat, lon = None, None

            for item in record.items:
                if item.item_type == CAT021ItemType.POSITION_WGS84_HIGH_RES:
                    lat = item.value.get('latitude')
                    lon = item.value.get('longitude')

                    if (AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lat_min'] <= lat <=
                            AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lat_max'] and
                            AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lon_min'] <= lon <=
                            AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lon_max']):
                        has_valid_position = True

                if item.item_type == CAT021ItemType.TARGET_REPORT_DESCRIPTOR:
                    gbs = item.value.get('GBS', 0)
                    if gbs == 1:
                        is_ground = True

            if has_valid_position and not is_ground:
                filtered_records.append(record)

        return filtered_records

    @staticmethod
    def filter_dataframe_cat021(df: pd.DataFrame) -> pd.DataFrame:
        """Filtra DataFrame CAT021: área geográfica + eliminar ground"""
        df = df.copy()

        if 'LAT' in df.columns and 'LON' in df.columns:
            geo_mask = (
                    (df['LAT'] >= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lat_min']) &
                    (df['LAT'] <= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lat_max']) &
                    (df['LON'] >= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lon_min']) &
                    (df['LON'] <= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lon_max'])
            )
            df = df[geo_mask]

        if 'GBS' in df.columns:
            df = df[df['GBS'] != 1]

        return df

    @staticmethod
    def filter_dataframe_cat048(df: pd.DataFrame) -> pd.DataFrame:
        """Filtra DataFrame CAT048: área geográfica"""
        df = df.copy()

        if 'LAT' in df.columns and 'LON' in df.columns:
            geo_mask = (
                    (df['LAT'] >= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lat_min']) &
                    (df['LAT'] <= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lat_max']) &
                    (df['LON'] >= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lon_min']) &
                    (df['LON'] <= AsterixPreprocessor.GEOGRAPHIC_BOUNDS['lon_max'])
            )
            df = df[geo_mask]

        return df

    @staticmethod
    def apply_qnh_correction(df: pd.DataFrame, qnh: float = QNH_STANDARD) -> pd.DataFrame:
        """Aplica corrección QNH a aeronaves < 6000 ft"""
        df = df.copy()

        qnh_correction = (qnh - AsterixPreprocessor.QNH_STANDARD) * 30

        if 'ALT_ft' in df.columns:
            df['ALT_QNH_ft'] = df['ALT_ft'].copy()
            below_ta = df['ALT_ft'] < AsterixPreprocessor.TRANSITION_ALTITUDE
            df.loc[below_ta, 'ALT_QNH_ft'] = df.loc[below_ta, 'ALT_ft'] + qnh_correction

        elif 'FL' in df.columns:
            df['ALT_ft'] = df['FL'] * 100
            df['ALT_QNH_ft'] = df['ALT_ft'].copy()
            below_ta = df['ALT_ft'] < AsterixPreprocessor.TRANSITION_ALTITUDE
            df.loc[below_ta, 'ALT_QNH_ft'] = df.loc[below_ta, 'ALT_ft'] + qnh_correction

        return df

    @staticmethod
    def apply_qnh_with_bp(df: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica corrección QNH usando BP de cada aeronave
        Si BP cambia a 1013 antes de 6000ft, usa BP anterior
        """
        df = df.copy()

        if 'BP' not in df.columns or 'ALT_ft' not in df.columns:
            return AsterixPreprocessor.apply_qnh_correction(df)

        df['ALT_QNH_ft'] = df['ALT_ft'].copy()

        for aircraft in df['TA'].unique():
            mask = df['TA'] == aircraft
            aircraft_data = df[mask].sort_values('Time')

            previous_bp = None

            for idx in aircraft_data.index:
                altitude = df.loc[idx, 'ALT_ft']
                current_bp = df.loc[idx, 'BP']

                if pd.notna(altitude) and altitude < AsterixPreprocessor.TRANSITION_ALTITUDE:
                    if pd.notna(current_bp):
                        bp_to_use = current_bp if current_bp != AsterixPreprocessor.QNH_STANDARD else previous_bp

                        if bp_to_use and bp_to_use != AsterixPreprocessor.QNH_STANDARD:
                            correction = (bp_to_use - AsterixPreprocessor.QNH_STANDARD) * 30
                            df.loc[idx, 'ALT_QNH_ft'] = altitude + correction

                if pd.notna(current_bp) and current_bp != AsterixPreprocessor.QNH_STANDARD:
                    previous_bp = current_bp

        return df
