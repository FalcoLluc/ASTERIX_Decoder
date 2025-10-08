import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT048ItemType
from src.utils.cat048_corrections import QNHCorrector


class Cat048CSVExporter:
    """Export CAT048 decoded records to pandas DataFrame with one row per record"""
    def __init__(self):
        self._qnh = QNHCorrector()

    def records_to_dataframe(self, records: List[Record]) -> pd.DataFrame:
        """
        Convert list of Record objects to a pandas DataFrame.
        Each row represents ONE record with all fields flattened.
        """
        rows = []

        for record in records:
            row = {
                'CAT': record.category.value,
                'SAC': None,
                'SIC': None,
            }

            # Collect inputs for QNH correction
            ta_hex = None
            fl = None
            bp = None

            for item in record.items:
                item_type = item.item_type
                value = item.value

                if item_type == CAT048ItemType.DATA_SOURCE_IDENTIFIER:
                    row['SAC'] = value.get('SAC')
                    row['SIC'] = value.get('SIC')

                elif item_type == CAT048ItemType.TIME_OF_DAY:
                    row['Time'] = value.get('total_seconds')

                elif item_type == CAT048ItemType.TARGET_REPORT_DESCRIPTOR:
                    row['TYP'] = value.get('TYP')
                    row['SIM'] = value.get('SIM')
                    row['SPI'] = value.get('SPI')

                elif item_type == CAT048ItemType.MEASURED_POSITION_POLAR:
                    row['RHO'] = value.get('RHO_nm')
                    row['THETA'] = value.get('THETA_degrees')

                elif item_type == CAT048ItemType.MODE_3A_CODE:
                    row['Mode3/A'] = value.get('Mode3/A')
                    row['V'] = value.get('V')
                    row['G'] = value.get('G')
                    row['L'] = value.get('L')

                elif item_type == CAT048ItemType.FLIGHT_LEVEL:
                    row['FL'] = value.get('FL')
                    row['FL_V'] = value.get('V')
                    row['FL_G'] = value.get('G')
                    fl = value.get('FL')

                elif item_type == CAT048ItemType.RADAR_PLOT_CHARACTERISTICS:
                    row['SRL'] = value.get('SRL')
                    row['SRR'] = value.get('SRR')
                    row['SAM'] = value.get('SAM')

                elif item_type == CAT048ItemType.AIRCRAFT_ADDRESS:
                    ta_hex = value.get('aircraft_address_hex')
                    row['TA'] = ta_hex

                elif item_type == CAT048ItemType.AIRCRAFT_IDENTIFICATION:
                    row['TI'] = value.get('TI')

                elif item_type == CAT048ItemType.TRACK_NUMBER:
                    row['TN'] = value.get('TN')

                elif item_type == CAT048ItemType.TRACK_VELOCITY_POLAR:
                    row['CALC_GS'] = value.get('GS_kt')
                    row['CALC_HDG'] = value.get('HDG_degrees')

                elif item_type == CAT048ItemType.TRACK_STATUS:
                    row['CNF'] = value.get('CNF')
                    row['RAD'] = value.get('RAD')
                    row['CDM'] = value.get('CDM')

                elif item_type == CAT048ItemType.COMMUNICATIONS_ACAS:
                    row['COM'] = value.get('COM')
                    row['STAT'] = value.get('STAT')
                    row['STAT_DESC'] = value.get('STAT_description')

                elif item_type == CAT048ItemType.MODE_S_MB_DATA:
                    bds_registers = value.get('bds_registers', [])
                    for bds_reg in bds_registers:
                        # BDS 4.0 fields
                        if 'MCP_FCU_ALT_ft' in bds_reg:
                            row['MCP_FCU_ALT'] = bds_reg['MCP_FCU_ALT_ft']
                        if 'FMS_ALT_ft' in bds_reg:
                            row['FMS_ALT'] = bds_reg['FMS_ALT_ft']
                        if 'BP_mb' in bds_reg:
                            bp = bds_reg['BP_mb']
                            row['BP'] = bp

                        # BDS 5.0 fields
                        if 'RA_deg' in bds_reg:
                            row['RA'] = bds_reg['RA_deg']
                        if 'TTA_deg' in bds_reg:
                            row['TTA'] = bds_reg['TTA_deg']
                        if 'GS_kt' in bds_reg:
                            row['GS'] = bds_reg['GS_kt']
                        if 'TAR_deg_s' in bds_reg:
                            row['TAR'] = bds_reg['TAR_deg_s']
                        if 'TAS_kt' in bds_reg:
                            row['TAS'] = bds_reg['TAS_kt']

                        # BDS 6.0 fields
                        if 'MG_HDG_deg' in bds_reg:
                            row['HDG'] = bds_reg['MG_HDG_deg']
                        if 'IAS_kt' in bds_reg:
                            row['IAS'] = bds_reg['IAS_kt']
                        if 'MACH' in bds_reg:
                            row['MACH'] = bds_reg['MACH']
                        if 'BAR_RATE_ft_min' in bds_reg:
                            row['BAR'] = bds_reg['BAR_RATE_ft_min']
                        if 'IVV_ft_min' in bds_reg:
                            row['IVV'] = bds_reg['IVV_ft_min']

            # Apply QNH correction at the end of parsing the record
            alt_qnh_ft, corrected = self._qnh.correct(ta_hex, fl, bp)
            if alt_qnh_ft is not None:
                row['ALT_QNH_ft'] = alt_qnh_ft
                row['QNH_CORRECTED'] = corrected

            rows.append(row)

        df = pd.DataFrame(rows)

        column_order = [
            'CAT', 'SAC', 'SIC', 'Time', 'TYP', 'SIM', 'SPI',
            'RHO', 'THETA', 'Mode3/A', 'V', 'G', 'L',
            'FL', 'ALT_QNH_ft', 'QNH_CORRECTED', 'FL_V', 'FL_G',
            'SRL', 'SRR', 'SAM',
            'TA', 'TI', 'TN',
            'CALC_GS', 'CALC_HDG',
            'CNF', 'RAD', 'CDM',
            'COM', 'STAT', 'STAT_DESC',
            'MCP_FCU_ALT', 'FMS_ALT', 'BP',
            'RA', 'TTA', 'GS', 'TAR', 'TAS',
            'HDG', 'IAS', 'MACH', 'BAR', 'IVV'
        ]

        # Reorder columns (only include existing columns first, then keep any extras)
        existing_columns = [col for col in column_order if col in df.columns]
        remaining = [c for c in df.columns if c not in existing_columns]
        df = df[existing_columns + remaining]
        return df

    @staticmethod
    def export_to_csv(records: List[Record], output_path: str):
        """Export records directly to CSV file"""
        exporter = Cat048CSVExporter()
        df = exporter.records_to_dataframe(records)
        df.to_csv(output_path, index=False, na_rep='N/A')
        return df

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
