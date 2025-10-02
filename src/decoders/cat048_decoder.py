from src.decoders.asterix_decoder_base import AsterixDecoderBase
from src.types.enums import CAT048ItemType
from src.models.record import Record
from src.models.item import Item
from typing import List

class Cat048Decoder(AsterixDecoderBase):
    def __init__(self):
        # Map FSPEC bits (item types) to decoding methods
        self.decoder_map = {
            CAT048ItemType.DATA_SOURCE_IDENTIFIER: self._decode_data_source,
            CAT048ItemType.TIME_OF_DAY: self._decode_time_of_day,
            CAT048ItemType.TARGET_REPORT_DESCRIPTOR: self._decode_target_report_descriptor,
            CAT048ItemType.MEASURED_POSITION_POLAR: self._decode_measured_position_polar,
            CAT048ItemType.MODE_3A_CODE: self._decode_mode_3a_code,
            CAT048ItemType.FLIGHT_LEVEL: self._decode_flight_level,
            CAT048ItemType.RADAR_PLOT_CHARACTERISTICS: self._decode_radar_plot_characteristics,
            CAT048ItemType.AIRCRAFT_ADDRESS: self._decode_aircraft_address,
            CAT048ItemType.AIRCRAFT_IDENTIFICATION: self._decode_aircraft_identification,
            CAT048ItemType.MODE_S_MB_DATA: self._decode_mode_s_mb_data,
            CAT048ItemType.TRACK_NUMBER: self._decode_track_number,
            CAT048ItemType.TRACK_VELOCITY_POLAR: self._decode_track_velocity_polar,
            CAT048ItemType.TRACK_STATUS: self._decode_track_status,
            CAT048ItemType.COMMUNICATIONS_ACAS: self._decode_communications_acas,
        }

    def decode_record(self, record: Record) -> Record:
        """Main decoding method"""
        # Parse FSPEC to get list of items in order
        fspec_items, data_start = self._parse_fspec(record)

        # Initialize pointer to data after FSPEC
        data_pointer = data_start

        # Decode each item in FSPEC order
        for item_type in fspec_items:
            decoder_func = self.decoder_map.get(item_type)
            if decoder_func:
                # Each decoder returns the new data pointer position
                data_pointer = decoder_func(data_pointer, record)
            else:
                print(f"Warning: No decoder for CAT048 item {item_type}")
                # Skip this item - we need to know its length to continue
                # For now, break (we'll implement proper length detection)
                break

        return record

    # DE MOM PODRIA SER ESTATIC PERO SI DESPRES AGAFA ELS PARAMETRES DEL CONSTRUCTOR SI QUE SERA METODE
    def _parse_fspec(self, record: Record) -> tuple[List[CAT048ItemType], int]:
        """
        Parse Field Specification to determine which data items are present.
        Returns: (list of item types in order, position where data starts)
        """
        raw_data = record.raw_data
        fspec_items = []
        position = 0
        frn = 1

        while position < len(raw_data):
            byte = raw_data[position]
            position += 1

            # Extract field indicators (bits 7-1, bit 0 is FX)
            for bit in range(7, 0, -1):
                # 0 is not included, so will stop before reaching FX
                if byte & (1 << bit):
                    # it makes an AND operation to check if the bit is present
                    try:
                        # if present, try to parse the ItemType
                        item_type = CAT048ItemType(frn)
                        fspec_items.append(item_type)
                    except ValueError:
                        print(f"Warning: Unknown FRN {frn} in FSPEC")

                # frn will be increasing, but only if AND is successfully an item is added
                frn += 1

            # Check FX bit - if 0, this is the last FSPEC byte
            if not (byte & 0x01):
                # break exits the loop
                break

        return fspec_items, position

    # DECODER METHODS - IMPLEMENT THESE STEP BY STEP
    def _decode_data_source(self, pos: int, record: Record) -> int:
        """I048/010 - Data Source Identifier (2 bytes)"""
        data=record.raw_data
        if pos + 2 > len(data):
            return pos

        sac = data[pos]  # System Area Code
        sic = data[pos + 1]  # System Identification Code

        item = Item(
            item_offset=pos,
            length=2,
            frn=1,
            item_type=CAT048ItemType.DATA_SOURCE_IDENTIFIER,
            value={"SAC": sac, "SIC": sic}
        )
        record.items.append(item)

        return pos + 2

    def _decode_time_of_day(self, pos: int, record: Record) -> int:
        """I048/140 - Time of Day (3 bytes)
        Spec: The time information, coded in three octets, shall reflect the exact
        time of an event, expressed as a number of 1/128 s elapsed since
        last midnight.
        """
        data = record.raw_data
        if pos + 3 > len(data):
            return pos

        # Read 3 bytes and convert to integer (big-endian)
        time_bytes = data[pos:pos + 3]
        time_128_seconds = int.from_bytes(time_bytes, byteorder='big')

        # Convert to seconds (divide by 128 since each unit = 1/128 second)
        total_seconds = time_128_seconds / 128.0

        # Calculate hours, minutes, seconds
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60

        # Format as time string
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

        item = Item(
            item_offset=pos,
            length=3,
            frn=2,
            item_type=CAT048ItemType.TIME_OF_DAY,
            value={
                "raw_bytes": list(time_bytes),
                "time_128_seconds": time_128_seconds,
                "total_seconds": total_seconds,
                "time_string": time_str,
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds
            }
        )
        record.items.append(item)

        return pos + 3

    def _decode_target_report_descriptor(self, pos: int, record: Record) -> int:
        """I048/020 - Target Report Descriptor (1 byte)"""
        data=record.raw_data
        if pos + 1 > len(data):
            return pos

        # TODO: Implement descriptor decoding
        item = Item(
            item_offset=pos,
            length=1,
            frn=3,
            item_type=CAT048ItemType.TARGET_REPORT_DESCRIPTOR,
            value={"raw": data[pos]}
        )
        record.items.append(item)

        # TODO: SHA DE MIRAR SI ES VARIABLE
        return pos + 1

    def _decode_measured_position_polar(self, pos: int, record: Record) -> int:
        """I048/040 - Measured Position in Polar Coordinates (4 bytes)"""
        data = record.raw_data
        if pos + 4 > len(data):
            return pos

        # Read 4 bytes
        position_bytes = data[pos:pos + 4]

        # Extract RHO (range) - first 2 bytes (16 bits)
        rho_bytes = position_bytes[0:2]
        rho_256_nm = int.from_bytes(rho_bytes, byteorder='big')

        # Extract THETA (angle) - last 2 bytes (16 bits)
        theta_bytes = position_bytes[2:4]
        theta_units = int.from_bytes(theta_bytes, byteorder='big')

        # Convert RHO to nautical miles (bit-17 (LSB) = 1/256 NM)
        range_nm = rho_256_nm / 256.0

        # Convert THETA to degrees (1 LSB = 360°/65536 ≈ 0.0055°)
        theta_degrees = (theta_units * 360.0) / 65536.0

        # Normalize angle to 0-360 degrees
        theta_degrees %= 360.0

        item = Item(
            item_offset=pos,
            length=4,
            frn=4,
            item_type=CAT048ItemType.MEASURED_POSITION_POLAR,
            value={
                "raw_bytes": list(position_bytes),
                "rho_256_nm": rho_256_nm,
                "theta_units": theta_units,
                "range_nm": range_nm,
                "angle_degrees": theta_degrees,
                "formatted": f"Range: {range_nm:.3f} NM, Angle: {theta_degrees:.3f}°"
            }
        )
        record.items.append(item)

        return pos + 4

    # Add the other decoder methods with the same pattern...
    def _decode_mode_3a_code(self, pos: int, record: Record) -> int:
        """I048/070 - Mode-3/A Code (2 bytes)"""
        return pos + 2  # Placeholder

    def _decode_flight_level(self, pos: int, record: Record) -> int:
        """I048/090 - Flight Level (2 bytes)"""
        return pos + 2  # Placeholder

    # ... continue with all other methods


    def _decode_radar_plot_characteristics(self, pos: int, record: Record) -> int:
        """I048/130 - Radar Plot Characteristics (1 byte)"""
        data=record.raw_data
        if pos + 1 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=1,
            frn=7,
            item_type=CAT048ItemType.RADAR_PLOT_CHARACTERISTICS,
            value={"raw": data[pos]}
        )
        record.items.append(item)

        # TODO: SHA DE MIRAR SI ES VARIABLE
        return pos + 1

    def _decode_aircraft_address(self, pos: int, record: Record) -> int:
        """I048/220 - Aircraft Address (3 bytes)"""
        data=record.raw_data
        if pos + 3 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=3,
            frn=8,
            item_type=CAT048ItemType.AIRCRAFT_ADDRESS,
            value={"raw": data[pos:pos + 3]}
        )
        record.items.append(item)

        return pos + 3

    def _decode_aircraft_identification(self, pos: int, record: Record) -> int:
        """I048/240 - Aircraft Identification (6 bytes)"""
        data=record.raw_data
        if pos + 6 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=6,
            frn=9,
            item_type=CAT048ItemType.AIRCRAFT_IDENTIFICATION,
            value={"raw": data[pos:pos + 6]}
        )
        record.items.append(item)

        return pos + 6

    def _decode_mode_s_mb_data(self, pos: int, record: Record) -> int:
        """I048/250 - Mode S MB Data (8 bytes)"""
        data=record.raw_data
        if pos + 8 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=8,
            frn=10,
            item_type=CAT048ItemType.MODE_S_MB_DATA,
            value={"raw": data[pos:pos + 8]}
        )
        record.items.append(item)

        # TODO: SHA DE MIRAR SI ES VARIABLE
        return pos + 8

    def _decode_track_number(self, pos: int, record: Record) -> int:
        """I048/161 - Track Number (2 bytes)"""
        data=record.raw_data
        if pos + 2 > len(data):
            return pos

        track_number = int.from_bytes(data[pos:pos + 2], byteorder='big')

        item = Item(
            item_offset=pos,
            length=2,
            frn=11,
            item_type=CAT048ItemType.TRACK_NUMBER,
            value=track_number
        )
        record.items.append(item)

        return pos + 2

    def _decode_track_velocity_polar(self, pos: int, record: Record) -> int:
        """I048/200 - Track Velocity in Polar Representation (4 bytes)"""
        data=record.raw_data
        if pos + 4 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=4,
            frn=13,
            item_type=CAT048ItemType.TRACK_VELOCITY_POLAR,
            value={"raw": data[pos:pos + 4]}
        )
        record.items.append(item)

        return pos + 4

    def _decode_track_status(self, pos: int, record: Record) -> int:
        """I048/170 - Track Status (2 bytes)"""
        data=record.raw_data
        if pos + 2 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=2,
            frn=14,
            item_type=CAT048ItemType.TRACK_STATUS,
            value={"raw": data[pos:pos + 2]}
        )
        record.items.append(item)

        # TODO: SHA DE MIRAR SI ES VARIABLE
        return pos + 2

    def _decode_communications_acas(self, pos: int, record: Record) -> int:
        """I048/230 - Communications/ACAS Capability (2 byte)"""
        data=record.raw_data
        if pos + 1 > len(data):
            return pos

        item = Item(
            item_offset=pos,
            length=1,
            frn=21,
            item_type=CAT048ItemType.COMMUNICATIONS_ACAS,
            value={"raw": data[pos]}
        )
        record.items.append(item)

        return pos + 2