import pandas as pd
from src.utils.qnh_corrector import QNHCorrector


class AsterixPreprocessor:
    """Centralized preprocessing for ASTERIX data"""

    LAT_MIN = 40.99
    LAT_MAX = 41.7
    LON_MIN = 1.5
    LON_MAX = 2.6

    @staticmethod
    def process_cat048(df: pd.DataFrame, apply_filters: bool = True, apply_qnh: bool = True) -> pd.DataFrame:
        """Apply CAT048 preprocessing pipeline"""
        df = df.copy()

        # Sort by time and aircraft address (not callsign)
        if 'Time' in df.columns and 'Target_address' in df.columns:
            df = df.sort_values(['Time', 'Target_address'], na_position='last').reset_index(drop=True)

        if apply_qnh:
            df = AsterixPreprocessor._apply_qnh_correction(df)

        if apply_filters:
            df = AsterixPreprocessor._filter_geographic(df)

        return df

    @staticmethod
    def process_cat021(df: pd.DataFrame, apply_filters: bool = True,
                       apply_qnh: bool = False) -> pd.DataFrame:
        """Apply CAT021 preprocessing pipeline"""
        df = df.copy()

        # Sort by time and aircraft address (not callsign)
        if 'Time' in df.columns and 'Target_address' in df.columns:
            df = df.sort_values(['Time', 'Target_address'], na_position='last').reset_index(drop=True)

        if apply_qnh:
            df = AsterixPreprocessor._apply_qnh_correction(df)

        if apply_filters:
            df = AsterixPreprocessor._filter_geographic(df)
            df = AsterixPreprocessor._filter_ground(df)

        return df

    @staticmethod
    def _apply_qnh_correction(df: pd.DataFrame) -> pd.DataFrame:
        """Apply QNH correction using aircraft address for state tracking"""
        if 'Flight_Level' not in df.columns or 'Target_address' not in df.columns:
            return df

        if 'h_ft' not in df.columns:
            raise ValueError("h_ft column must exist in DataFrame")

        df = df.copy()

        corrector = QNHCorrector()
        alt_qnh_list = []
        qnh_corrected_list = []

        for _, row in df.iterrows():
            ta = row.get('Target_address')
            fl = row.get('Flight_Level')
            bp = row.get('BP')

            alt_qnh, corrected = corrector.correct(ta, fl, bp)
            alt_qnh_list.append(alt_qnh)
            qnh_corrected_list.append(corrected)

        df['h_ft'] = alt_qnh_list
        df['ModeC_corrected'] = qnh_corrected_list

        return df

    @staticmethod
    def _filter_geographic(df: pd.DataFrame) -> pd.DataFrame:
        """Filter to project geographic bounds"""
        if 'Latitud' not in df.columns or 'Longitud' not in df.columns:
            return df

        mask = (
            (df['Latitud'] >= AsterixPreprocessor.LAT_MIN) &
            (df['Latitud'] <= AsterixPreprocessor.LAT_MAX) &
            (df['Longitud'] >= AsterixPreprocessor.LON_MIN) &
            (df['Longitud'] <= AsterixPreprocessor.LON_MAX)
        )
        return df[mask].reset_index(drop=True)

    @staticmethod
    def _filter_ground(df: pd.DataFrame) -> pd.DataFrame:
        """Remove ground targets (CAT021 only, GBS=1)"""
        if 'GBS' not in df.columns:
            return df
        return df[df['GBS'] != 1].reset_index(drop=True)

    @staticmethod
    def export_to_csv(df: pd.DataFrame, output_path: str, na_rep: str = 'N/A'):
        """Export DataFrame to CSV"""
        df.to_csv(output_path, index=False, na_rep=na_rep)
        print(f"✅ Exported {len(df):,} records to {output_path}")
