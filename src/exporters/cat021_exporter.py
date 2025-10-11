import pandas as pd
from typing import List
from src.models.record import Record
from src.types.enums import CAT021ItemType


class Cat021Exporter:

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
                    row['BP'] = value.get('BP')

            rows.append(row)

        df = pd.DataFrame(rows)

        # Define column order
        column_order = [
            'CAT', 'SAC', 'SIC', 'Time',
            'ATP', 'ARC', 'RC', 'RAB', 'DCR', 'GBS', 'SIM', 'TST',
            'LAT', 'LON',
            'TA',
            'Mode3/A',
            'FL', 'ALT_ft',
            'ALT_QNH_ft',  # ✅ Pre-create for preprocessor
            'QNH_CORRECTED',  # ✅ Pre-create for preprocessor
            'TI',
            'BP'
        ]

        # Add missing QNH columns if not present (will be filled by preprocessor)
        for col in ['ALT_QNH_ft', 'QNH_CORRECTED']:
            if col not in df.columns:
                df[col] = None

        # Reorder columns (only include existing columns)
        existing_columns = [col for col in column_order if col in df.columns]

        # Add any remaining columns not in order
        remaining = [col for col in df.columns if col not in existing_columns]

        return df[existing_columns + remaining]
