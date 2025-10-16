import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT021ItemType, CAT048ItemType, Category
from src.utils.qnh_corrector import QNHCorrector


class AsterixExporter:
    """
    Unified exporter for all ASTERIX categories with preprocessing capabilities.
    Handles CAT021 and CAT048 records in a single DataFrame with shared and category-specific columns.
    """

    ALL_COLUMNS = [
        # Common fields
        'CAT',
        'SAC',
        'SIC',
        'Time',
        'Time_sec',
        'LAT',
        'LON',
        'H(m)',
        'H(ft)',
        'RHO',
        'THETA',
        'Mode3/A',
        'FL',
        'TA',
        'TI',
        'ModeS',
        'BP',
        'RA',
        'TTA',
        'GS',
        'TAR',
        'TAS',
        'HDG',
        'IAS',
        'MACH',
        'BAR',
        'IVV',
        'TN',
        'GS(kt)',
        'STAT',

        # Detection/Quality fields
        'TYP',  # CAT048: Detection type (PSR/SSR/Mode S)
        'SIM',  # Simulated target indicator (both categories)
        'RDP',  # CAT048: RDP Chain
        'SPI',  # CAT048: Special Position Identification
        'RAB',  # Report from field monitor (both categories)

        # CAT021-specific fields
        'H_WGS84',
        'ATP',
        'ARC',
        'RC',
        'DCR',
        'GBS',
        'TST',
    ]

    @staticmethod
    def records_to_dataframe(records: List[Record], apply_qnh: bool = True) -> pd.DataFrame:
        """
        Convert a mixed list of Record objects (any category) to a unified pandas DataFrame.
        Optionally applies QNH correction during export.

        Args:
            records: List of Record objects from any ASTERIX category
            apply_qnh: Whether to apply QNH correction (default: True)

        Returns:
            pd.DataFrame with unified schema
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

        # Sort by time and aircraft address
        if 'Time' in df.columns and 'TA' in df.columns:
            df = df.sort_values(['Time', 'TA'], na_position='last').reset_index(drop=True)

        # Apply QNH correction if requested
        if apply_qnh:
            df = AsterixExporter._apply_qnh_correction(df)

        return df

    @staticmethod
    def _apply_qnh_correction(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply QNH correction using aircraft address for state tracking.
        Only populates H(ft) and H(m) for records below transition altitude with valid QNH.
        """
        if 'FL' not in df.columns or 'TA' not in df.columns:
            return df

        df = df.copy()

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

        df['H(ft)'] = alt_ft_list
        df['H(m)'] = alt_m_list

        return df

    @staticmethod
    def _process_cat021(record: Record, row: dict) -> None:
        """Process CAT021-specific items and populate row dictionary."""
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
                row['SIM'] = value.get('SIM')  # Simulated target
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
                altitude_feet = value.get('altitude_feet')
                row['H_WGS84'] = altitude_feet
                # H(ft) and H(m) will be filled by QNH correction if applicable

            elif item_type == CAT021ItemType.TARGET_IDENTIFICATION:
                row['TI'] = value.get('callsign')

            elif item_type == CAT021ItemType.RESERVED_EXPANSION_FIELD:
                row['BP'] = value.get('BP')

    @staticmethod
    def _process_cat048(record: Record, row: dict) -> None:
        """Process CAT048-specific items and populate row dictionary."""
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

            elif item_type == CAT048ItemType.MODE_3A_CODE:
                row['Mode3/A'] = value.get('Mode3/A')

            elif item_type == CAT048ItemType.FLIGHT_LEVEL:
                row['FL'] = value.get('FL')
                # H(ft) and H(m) will be filled by QNH correction if applicable

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

            elif item_type == CAT048ItemType.TARGET_REPORT_DESCRIPTOR:
                # Extract all fields from Target Report Descriptor
                row['TYP'] = value.get('TYP')  # Detection type
                row['SIM'] = value.get('SIM')  # Simulated target
                row['RDP'] = value.get('RDP')  # RDP Chain
                row['SPI'] = value.get('SPI')  # Special Position Identification
                row['RAB'] = value.get('RAB')  # Report from field monitor

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

        if bds_present:
            row['ModeS'] = ' '.join(bds_present)

    @staticmethod
    def export_to_csv(df: pd.DataFrame, output_path: str, na_rep: str = 'N/A'):
        """Export DataFrame to CSV"""
        df.to_csv(output_path, index=False, na_rep=na_rep)
        print(f"✅ Exported {len(df):,} records to {output_path}")
