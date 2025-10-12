import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT021ItemType


class Cat021Exporter:
    """Export CAT021 decoded records to pandas DataFrame with one row per record"""

    @staticmethod
    def records_to_dataframe(records: List[Record]) -> pd.DataFrame:
        """
        Convert list of Record objects to a pandas DataFrame.
        Each row represents ONE record with all fields flattened.
        """
        rows = []

        for record in records:
            # Initialize row with consistent column names
            row = {
                'CAT': record.category.value,
                'SAC': None,
                'SIC': None,
                'Time': None,
                'Latitud': None,
                'Longitud': None,
                'ATP': None,
                'ARC': None,
                'RC': None,
                'RAB': None,
                'DCR': None,
                'GBS': None,
                'SIM': None,
                'TST': None,
                'Target_address': None,
                'Mode_3A': None,
                'Flight_Level': None,
                'h_ft': None,              # ADS-B geometric altitude
                'ModeC_corrected': None,   # QNH correction flag (if applied)
                'Target_identification': None,
                'BP': None
            }

            # Extract all items and flatten into single row
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
                    row['Latitud'] = value.get('latitude')
                    row['Longitud'] = value.get('longitude')

                elif item_type == CAT021ItemType.TARGET_ADDRESS:
                    row['Target_address'] = value.get('target_address_hex')

                elif item_type == CAT021ItemType.TIME_MESSAGE_RECEPTION_POSITION:
                    row['Time'] = value.get('total_seconds')

                elif item_type == CAT021ItemType.MODE_3A_CODE:
                    row['Mode_3A'] = value.get('mode_3a_code')

                elif item_type == CAT021ItemType.FLIGHT_LEVEL:
                    row['Flight_Level'] = value.get('flight_level')
                    row['h_ft'] = value.get('altitude_feet')  # Geometric altitude from ADS-B

                elif item_type == CAT021ItemType.TARGET_IDENTIFICATION:
                    row['Target_identification'] = value.get('callsign')

                elif item_type == CAT021ItemType.RESERVED_EXPANSION_FIELD:
                    row['BP'] = value.get('BP')  # Barometric pressure setting

            rows.append(row)

        # Create DataFrame - columns already in correct order from dict
        return pd.DataFrame(rows)
