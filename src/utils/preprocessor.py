import pandas as pd
from src.utils.qnh_corrector import QNHCorrector


class AsterixPreprocessor:
    """Centralized preprocessing for ASTERIX data"""

    # Geographic bounds from project specification
    LAT_MIN = 40.99
    LAT_MAX = 41.7
    LON_MIN = 1.5
    LON_MAX = 2.6

    @staticmethod
    def process_cat048(df: pd.DataFrame, apply_filters: bool = True,
                       apply_qnh: bool = True) -> pd.DataFrame:
        """
        Apply CAT048 preprocessing pipeline:
        1. Sort by time
        2. QNH correction (requires FL, TA, BP)
        3. Geographic filtering (requires LAT, LON)
        """
        df = df.copy()

        # Sort by time (primary) and aircraft (secondary)
        if 'Time' in df.columns:
            df = df.sort_values(['Time', 'TA'], na_position='last').reset_index(drop=True)

        if apply_qnh:
            df = AsterixPreprocessor._apply_qnh_correction(df)

        if apply_filters:
            df = AsterixPreprocessor._filter_geographic(df)

        return df

    @staticmethod
    def process_cat021(df: pd.DataFrame, apply_filters: bool = True,
                       apply_qnh: bool = False) -> pd.DataFrame:
        """
        Apply CAT021 preprocessing pipeline:
        1. Sort by time
        2. Optional QNH correction
        3. Geographic filtering
        4. Remove ground targets (GBS=1)
        """
        df = df.copy()

        # Sort by time
        if 'Time' in df.columns:
            df = df.sort_values(['Time', 'TA'], na_position='last').reset_index(drop=True)

        if apply_qnh:
            df = AsterixPreprocessor._apply_qnh_correction(df)

        if apply_filters:
            df = AsterixPreprocessor._filter_geographic(df)
            df = AsterixPreprocessor._filter_ground(df)

        return df

    @staticmethod
    def _apply_qnh_correction(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply QNH correction (assumes DataFrame already sorted by Time).
        Updates ALT_QNH_ft and QNH_CORRECTED columns.
        """
        if 'FL' not in df.columns or 'TA' not in df.columns:
            return df

        if 'ALT_QNH_ft' not in df.columns or 'QNH_CORRECTED' not in df.columns:
            raise ValueError("ALT_QNH_ft and QNH_CORRECTED columns must exist in DataFrame")

        df = df.copy()

        # Group by aircraft and process in time order
        corrector = QNHCorrector()
        alt_qnh_list = []
        qnh_corrected_list = []

        for _, row in df.iterrows():
            ta = row.get('TA')
            fl = row.get('FL')
            bp = row.get('BP')

            alt_qnh, corrected = corrector.correct(ta, fl, bp)
            alt_qnh_list.append(alt_qnh)
            qnh_corrected_list.append(corrected)

        df['ALT_QNH_ft'] = alt_qnh_list
        df['QNH_CORRECTED'] = qnh_corrected_list

        return df

    @staticmethod
    def _filter_geographic(df: pd.DataFrame) -> pd.DataFrame:
        """Filter to project geographic bounds (Barcelona area)"""
        if 'LAT' not in df.columns or 'LON' not in df.columns:
            return df

        mask = (
                (df['LAT'] >= AsterixPreprocessor.LAT_MIN) &
                (df['LAT'] <= AsterixPreprocessor.LAT_MAX) &
                (df['LON'] >= AsterixPreprocessor.LON_MIN) &
                (df['LON'] <= AsterixPreprocessor.LON_MAX)
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
        """Export DataFrame to CSV with custom null representation"""
        df.to_csv(output_path, index=False, na_rep=na_rep)
        print(f"✅ Exported {len(df):,} records to {output_path}")
