import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT048ItemType


class Cat048Exporter:
    """Export CAT048 decoded records to pandas DataFrame with one row per record"""

    @staticmethod
    def records_to_dataframe(records: List[Record]) -> pd.DataFrame:
        """
        Convert list of Record objects to a pandas DataFrame.
        Each row represents ONE record with all fields flattened.
        """
        rows = []

        for record in records:
            # Start with base record info
            row = {
                'CAT': record.category.value,
                'SAC': None,
                'SIC': None,
            }

            # Extract all items and flatten into single row
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

                elif item_type == CAT048ItemType.RADAR_PLOT_CHARACTERISTICS:
                    row['SRL'] = value.get('SRL')
                    row['SRR'] = value.get('SRR')
                    row['SAM'] = value.get('SAM')

                elif item_type == CAT048ItemType.AIRCRAFT_ADDRESS:
                    row['TA'] = value.get('aircraft_address_hex')

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

            rows.append(row)

        # Create DataFrame
        df = pd.DataFrame(rows)

        # Define column order (includes QNH columns for preprocessor)
        column_order = [
            # Basic identifiers
            'CAT', 'SAC', 'SIC', 'Time',

            # Position (LAT/LON added by WGS84 conversion)
            'LAT', 'LON',

            # Target descriptor
            'TYP', 'SIM', 'SPI',

            # Polar coordinates
            'RHO', 'THETA',

            # Mode 3/A
            'Mode3/A', 'V', 'G', 'L',

            # Flight level & altitude
            'FL', 'FL_V', 'FL_G',
            'ALT_QNH_ft',  # Pre-create for preprocessor
            'QNH_CORRECTED',  # Pre-create for preprocessor

            # Radar characteristics
            'SRL', 'SRR', 'SAM',

            # Aircraft identification
            'TA', 'TI', 'TN',

            # BDS 4.0
            'BP', 'MCP_FCU_ALT', 'FMS_ALT',

            # BDS 5.0
            'RA', 'TTA', 'GS', 'TAR', 'TAS',

            # BDS 6.0
            'HDG', 'IAS', 'MACH', 'BAR', 'IVV',

            # Calculated velocity
            'CALC_GS', 'CALC_HDG',

            # Track status
            'CNF', 'RAD', 'CDM',

            # Communications/ACAS
            'COM', 'STAT', 'STAT_DESC'
        ]

        # Add missing QNH columns if not present (will be filled by preprocessor)
        for col in ['ALT_QNH_ft', 'QNH_CORRECTED', 'LAT', 'LON']:
            if col not in df.columns:
                df[col] = None

        # Reorder columns (only include existing columns)
        existing_columns = [col for col in column_order if col in df.columns]

        # Add any remaining columns not in the predefined order
        remaining = [col for col in df.columns if col not in existing_columns]

        return df[existing_columns + remaining]
