# src/exporters/cat048_exporter.py

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
            # Initialize row with your exact column names
            row = {
                'CAT': record.category.value,
                'SAC': None,
                'SIC': None,
                'Time': None,
                'Latitud': None,
                'Longitud': None,
                'h_wgs84': None,
                'h_ft': None,
                'RHO': None,
                'THETA': None,
                'Mode_3A': None,
                'Flight_Level': None,
                'ModeC_corrected': None,
                'Target_address': None,
                'Target_identification': None,
                'Mode_S': None,
                'BP': None,
                'RA': None,
                'TTA': None,
                'GS': None,
                'TAR': None,
                'TAS': None,
                'HDG': None,
                'IAS': None,
                'MACH': None,
                'BAR': None,
                'IVV': None,
                'Track_number': None,
                'Ground_Speed_kt': None,
                'Heading': None,
                'STAT230': None
            }

            # Track which BDS registers are present
            bds_present = []

            # Extract all items and flatten into single row
            for item in record.items:
                item_type = item.item_type
                value = item.value

                if item_type == CAT048ItemType.DATA_SOURCE_IDENTIFIER:
                    row['SAC'] = value.get('SAC')
                    row['SIC'] = value.get('SIC')

                elif item_type == CAT048ItemType.TIME_OF_DAY:
                    row['Time'] = value.get('total_seconds')

                elif item_type == CAT048ItemType.MEASURED_POSITION_POLAR:
                    row['RHO'] = value.get('RHO_nm')
                    row['THETA'] = value.get('THETA_degrees')

                elif item_type == CAT048ItemType.MODE_3A_CODE:
                    row['Mode_3A'] = value.get('Mode3/A')

                elif item_type == CAT048ItemType.FLIGHT_LEVEL:
                    row['Flight_Level'] = value.get('FL')

                elif item_type == CAT048ItemType.AIRCRAFT_ADDRESS:
                    row['Target_address'] = value.get('aircraft_address_hex')

                elif item_type == CAT048ItemType.AIRCRAFT_IDENTIFICATION:
                    row['Target_identification'] = value.get('TI')

                elif item_type == CAT048ItemType.TRACK_NUMBER:
                    row['Track_number'] = value.get('TN')

                elif item_type == CAT048ItemType.TRACK_VELOCITY_POLAR:
                    row['Ground_Speed_kt'] = value.get('GS_kt')
                    row['Heading'] = value.get('HDG_degrees')

                elif item_type == CAT048ItemType.COMMUNICATIONS_ACAS:
                    row['STAT230'] = value.get('STAT_description')

                elif item_type == CAT048ItemType.MODE_S_MB_DATA:
                    bds_registers = value.get('bds_registers', [])
                    for bds_reg in bds_registers:
                        # Track BDS code
                        bds_code = bds_reg.get('bds_code')
                        if bds_code:
                            bds_formatted = f"BDS {bds_code[0]}.{bds_code[1]}"
                            if bds_formatted not in bds_present:
                                bds_present.append(bds_formatted)

                        # BDS 4.0 - BP
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

            # Set Mode_S field with all BDS registers present
            if bds_present:
                row['Mode_S'] = ' '.join(bds_present)

            rows.append(row)

        # Create DataFrame - columns already in correct order from dict
        return pd.DataFrame(rows)
