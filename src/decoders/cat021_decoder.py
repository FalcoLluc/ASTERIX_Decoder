from src.decoders.asterix_decoder_base import AsterixDecoderBase
from src.types.enums import CAT021ItemType
from src.models.record import Record
from src.models.item import Item
from typing import List

############ FALTA FILTRAR I QNH

class Cat021Decoder(AsterixDecoderBase):
    def __init__(self):
        super().__init__()
        self.decoder_map = {
            # Items to decode
            CAT021ItemType.DATA_SOURCE_IDENTIFICATION: self._decode_data_source,  # FRN 1
            CAT021ItemType.TARGET_REPORT_DESCRIPTOR: self._decode_target_report_descriptor,  # FRN 2
            CAT021ItemType.POSITION_WGS84_HIGH_RES: self._decode_position_wgs84_high_res,  # FRN 7
            CAT021ItemType.TARGET_ADDRESS: self._decode_target_address,  # FRN 11
            CAT021ItemType.TIME_MESSAGE_RECEPTION_POSITION: self._decode_time_message_reception_position,  # FRN 12
            CAT021ItemType.MODE_3A_CODE: self._decode_mode_3a_code,  # FRN 19
            CAT021ItemType.FLIGHT_LEVEL: self._decode_flight_level,  # FRN 21
            CAT021ItemType.TARGET_IDENTIFICATION: self._decode_target_identification,  # FRN 29
            CAT021ItemType.RESERVED_EXPANSION_FIELD: self._decode_reserved_expansion_field,  # FRN 48 (RE-BPS)

            # Items to skip
            CAT021ItemType.TRACK_NUMBER: self._skip_fixed_2,
            CAT021ItemType.SERVICE_IDENTIFICATION: self._skip_fixed_1,
            CAT021ItemType.TIME_APPLICABILITY_POSITION: self._skip_fixed_3,
            CAT021ItemType.POSITION_WGS84: self._skip_fixed_6,
            CAT021ItemType.TIME_APPLICABILITY_VELOCITY: self._skip_fixed_3,
            CAT021ItemType.AIR_SPEED: self._skip_fixed_2,
            CAT021ItemType.TRUE_AIRSPEED: self._skip_fixed_2,
            CAT021ItemType.TIME_MESSAGE_RECEPTION_POSITION_HIGH_PRECISION: self._skip_fixed_4,
            CAT021ItemType.TIME_MESSAGE_RECEPTION_VELOCITY: self._skip_fixed_3,
            CAT021ItemType.TIME_MESSAGE_RECEPTION_VELOCITY_HIGH_PRECISION: self._skip_fixed_4,
            CAT021ItemType.GEOMETRIC_HEIGHT: self._skip_fixed_2,
            CAT021ItemType.QUALITY_INDICATORS: self._skip_variable,
            CAT021ItemType.MOPS_VERSION: self._skip_fixed_1,
            CAT021ItemType.ROLL_ANGLE: self._skip_fixed_2,
            CAT021ItemType.MAGNETIC_HEADING: self._skip_fixed_2,
            CAT021ItemType.TARGET_STATUS: self._skip_fixed_1,
            CAT021ItemType.BAROMETRIC_VERTICAL_RATE: self._skip_fixed_2,
            CAT021ItemType.GEOMETRIC_VERTICAL_RATE: self._skip_fixed_2,
            CAT021ItemType.AIRBORNE_GROUND_VECTOR: self._skip_fixed_4,
            CAT021ItemType.TRACK_ANGLE_RATE: self._skip_fixed_2,
            CAT021ItemType.TIME_ASTERIX_REPORT_TRANSMISSION: self._skip_fixed_3,
            CAT021ItemType.EMITTER_CATEGORY: self._skip_fixed_1,
            CAT021ItemType.MET_INFORMATION: self._skip_compound,
            CAT021ItemType.SELECTED_ALTITUDE: self._skip_fixed_2,
            CAT021ItemType.FINAL_STATE_SELECTED_ALTITUDE: self._skip_fixed_2,
            CAT021ItemType.TRAJECTORY_INTENT: self._skip_compound,
            CAT021ItemType.SERVICE_MANAGEMENT: self._skip_fixed_1,
            CAT021ItemType.AIRCRAFT_OPERATIONAL_STATUS: self._skip_fixed_1,
            CAT021ItemType.SURFACE_CAPABILITIES: self._skip_variable,
            CAT021ItemType.MESSAGE_AMPLITUDE: self._skip_fixed_1,
            CAT021ItemType.MODE_S_MB_DATA: self._skip_repetitive,
            CAT021ItemType.ACAS_RESOLUTION_ADVISORY: self._skip_fixed_7,
            CAT021ItemType.RECEIVER_ID: self._skip_fixed_1,
            CAT021ItemType.DATA_AGES: self._skip_compound,
        }

    def decode_record(self, record: Record) -> Record:
        # general decodification method
        self.logger.debug("Starting decode_record: offset=%s, raw_len=%s", getattr(record, 'block_offset', None),
                          len(record.raw_data))
        fspec_items, data_start = self._parse_fspec(record)
        self.logger.debug("Parsed FSPEC: %d items, data_start=%d", len(fspec_items), data_start)

        data_pointer = data_start

        for item_type in fspec_items:
            decoder_func = self.decoder_map.get(item_type)
            if decoder_func:
                data_pointer = decoder_func(data_pointer, record)
            else:
                self.logger.warning("No decoder for CAT021 item %s", item_type)
                break

        return record

    def _parse_fspec(self, record: Record) -> tuple[List[CAT021ItemType], int]:
        # specification parse
        raw_data = record.raw_data
        fspec_items = []
        position = 0
        frn = 1

        while position < len(raw_data):
            byte = raw_data[position]
            position += 1

            for bit in range(7, 0, -1):
                if byte & (1 << bit):
                    try:
                        item_type = CAT021ItemType(frn)
                        fspec_items.append(item_type)
                    except ValueError:
                        pass
                frn += 1

            if not (byte & 0x01):
                break

        return fspec_items, position

    # ========== DECODERS ==========

    def _decode_data_source(self, pos: int, record: Record) -> int:
        """I021/010 - Data Source Identification"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        sac = data[pos]
        sic = data[pos + 1]

        item = Item(
            item_offset=pos,
            length=2,
            frn=1,
            item_type=CAT021ItemType.DATA_SOURCE_IDENTIFICATION,
            value={"SAC": sac, "SIC": sic}
        )
        record.items.append(item)
        return pos + 2

    def _decode_target_report_descriptor(self, pos: int, record: Record) -> int:
        """I021/040 - Target Report Descriptor"""
        data = record.raw_data
        if pos >= len(data):
            return pos

        length = self._read_variable_length_item(pos, data)
        first_octet = data[pos]

        atp = (first_octet >> 5) & 0x07
        arc = (first_octet >> 3) & 0x03
        rc = (first_octet >> 2) & 0x01
        rab = (first_octet >> 1) & 0x01

        value = {
            "ATP": atp,
            "ARC": arc,
            "RC": rc,
            "RAB": rab
        }

        if length >= 2 and (first_octet & 0x01):
            second_octet = data[pos + 1]
            value["DCR"] = (second_octet >> 7) & 0x01
            value["GBS"] = (second_octet >> 6) & 0x01
            value["SIM"] = (second_octet >> 5) & 0x01
            value["TST"] = (second_octet >> 4) & 0x01
            value["SAA"] = (second_octet >> 3) & 0x01
            value["CL"] = (second_octet >> 1) & 0x03

        if length >= 3 and (data[pos + 1] & 0x01):
            third_octet = data[pos + 2]
            value["IPC"] = (third_octet >> 5) & 0x01
            value["NOGO"] = (third_octet >> 4) & 0x01
            value["CPR"] = (third_octet >> 3) & 0x01
            value["LDPJ"] = (third_octet >> 2) & 0x01
            value["RCF"] = (third_octet >> 1) & 0x01

        item = Item(
            item_offset=pos,
            length=length,
            frn=2,
            item_type=CAT021ItemType.TARGET_REPORT_DESCRIPTOR,
            value=value
        )
        record.items.append(item)
        return pos + length

    def _decode_position_wgs84_high_res(self, pos: int, record: Record) -> int:
        """I021/131 - High-Resolution Position in WGS-84"""
        data = record.raw_data
        if pos + 8 > len(data):
            return pos

        lat_raw = int.from_bytes(data[pos:pos + 4], byteorder='big', signed=True)
        lon_raw = int.from_bytes(data[pos + 4:pos + 8], byteorder='big', signed=True)

        # LSB = 180 / 2^30 degrees
        latitude = lat_raw * (180.0 / (2 ** 30))
        longitude = lon_raw * (180.0 / (2 ** 30))

        item = Item(
            item_offset=pos,
            length=8,
            frn=7,
            item_type=CAT021ItemType.POSITION_WGS84_HIGH_RES,
            value={
                "latitude": latitude,
                "longitude": longitude,
                "formatted": f"Lat: {latitude:.8f}°, Lon: {longitude:.8f}°"
            }
        )
        record.items.append(item)
        return pos + 8

    def _decode_target_address(self, pos: int, record: Record) -> int:
        """I021/080 - Target Address"""
        data = record.raw_data
        if pos + 3 > len(data):
            return pos

        address_bytes = data[pos:pos + 3]
        target_address = int.from_bytes(address_bytes, byteorder='big')
        target_address_hex = f"{target_address:06X}"

        item = Item(
            item_offset=pos,
            length=3,
            frn=11,
            item_type=CAT021ItemType.TARGET_ADDRESS,
            value={
                "target_address": target_address,
                "target_address_hex": target_address_hex
            }
        )
        record.items.append(item)
        return pos + 3

    def _decode_time_message_reception_position(self, pos: int, record: Record) -> int:
        """I021/073 - Time of Message Reception for Position"""
        data = record.raw_data
        if pos + 3 > len(data):
            return pos

        time_bytes = data[pos:pos + 3]
        time_128_seconds = int.from_bytes(time_bytes, byteorder='big')
        total_seconds = time_128_seconds / 128.0

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds - int(total_seconds)) * 1000)

        formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

        item = Item(
            item_offset=pos,
            length=3,
            frn=12,
            item_type=CAT021ItemType.TIME_MESSAGE_RECEPTION_POSITION,
            value={
                "total_seconds": total_seconds,
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds,
                "milliseconds": milliseconds,
                "formatted": formatted_time,
            }
        )
        record.items.append(item)
        return pos + 3

    def _decode_mode_3a_code(self, pos: int, record: Record) -> int:
        """I021/070 - Mode 3A Code"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        mode_3a_raw = int.from_bytes(data[pos:pos + 2], byteorder='big')
        mode_3a_code = mode_3a_raw & 0x0FFF

        a = (mode_3a_code >> 9) & 0x07
        b = (mode_3a_code >> 6) & 0x07
        c = (mode_3a_code >> 3) & 0x07
        d = mode_3a_code & 0x07

        mode_3a_octal = f"{a}{b}{c}{d}"

        item = Item(
            item_offset=pos,
            length=2,
            frn=19,
            item_type=CAT021ItemType.MODE_3A_CODE,
            value={
                "mode_3a_code": mode_3a_octal,
                "mode_3a_raw": mode_3a_code
            }
        )
        record.items.append(item)
        return pos + 2

    def _decode_flight_level(self, pos: int, record: Record) -> int:
        """I021/145 - Flight Level"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        fl_raw = int.from_bytes(data[pos:pos + 2], byteorder='big', signed=True)
        flight_level = fl_raw / 4.0

        item = Item(
            item_offset=pos,
            length=2,
            frn=21,
            item_type=CAT021ItemType.FLIGHT_LEVEL,
            value={
                "flight_level": flight_level,
                "altitude_feet": flight_level * 100
            }
        )
        record.items.append(item)
        return pos + 2

    def _decode_target_identification(self, pos: int, record: Record) -> int:
        """I021/170 - Target Identification"""
        data = record.raw_data
        if pos + 6 > len(data):
            return pos

        id_bytes = data[pos:pos + 6]
        id_value = int.from_bytes(id_bytes, byteorder='big')

        callsign = ""
        for i in range(8):
            shift = 42 - (i * 6)
            char_code = (id_value >> shift) & 0x3F

            if 1 <= char_code <= 26:
                char = chr(ord('A') + char_code - 1)
            elif char_code == 32:
                char = ' '
            elif 48 <= char_code <= 57:
                char = chr(char_code)
            else:
                char = ' '

            callsign += char

        callsign = callsign.rstrip()

        item = Item(
            item_offset=pos,
            length=6,
            frn=29,
            item_type=CAT021ItemType.TARGET_IDENTIFICATION,
            value={
                "callsign": callsign
            }
        )
        record.items.append(item)
        return pos + 6

    def _decode_reserved_expansion_field(self, pos: int, record: Record) -> int:
        """I021/RE - Reserved Expansion Field"""
        data = record.raw_data
        if pos >= len(data):
            return pos

        length = data[pos]
        if pos + length > len(data):
            return pos

        if pos + 1 < len(data):
            items_indicator = data[pos + 1]
            current_pos = pos + 2
            value = {}

            if items_indicator & 0x80 and current_pos + 1 < pos + length:
                bps_raw = int.from_bytes(data[current_pos:current_pos + 2], byteorder='big')
                bps_value = (bps_raw & 0x0FFF) * 0.1 + 800  # LSB = 0.1 hPa, offset 800
                value["BP"] = bps_value
                current_pos += 2

            item = Item(
                item_offset=pos,
                length=length,
                frn=48,
                item_type=CAT021ItemType.RESERVED_EXPANSION_FIELD,
                value=value
            )
            record.items.append(item)

        return pos + length

    # ========== SKIP METHODS ==========

    def _skip_fixed_1(self, pos: int, record: Record) -> int:
        """Skip 1-byte fixed item"""
        return pos + 1 if pos + 1 <= len(record.raw_data) else pos

    def _skip_fixed_2(self, pos: int, record: Record) -> int:
        """Skip 2-byte fixed item"""
        return pos + 2 if pos + 2 <= len(record.raw_data) else pos

    def _skip_fixed_3(self, pos: int, record: Record) -> int:
        """Skip 3-byte fixed item"""
        return pos + 3 if pos + 3 <= len(record.raw_data) else pos

    def _skip_fixed_4(self, pos: int, record: Record) -> int:
        """Skip 4-byte fixed item"""
        return pos + 4 if pos + 4 <= len(record.raw_data) else pos

    def _skip_fixed_6(self, pos: int, record: Record) -> int:
        """Skip 6-byte fixed item"""
        return pos + 6 if pos + 6 <= len(record.raw_data) else pos

    def _skip_fixed_7(self, pos: int, record: Record) -> int:
        """Skip 7-byte fixed item"""
        return pos + 7 if pos + 7 <= len(record.raw_data) else pos

    def _skip_variable(self, pos: int, record: Record) -> int:
        """Skip variable-length item with FX bit"""
        data = record.raw_data
        if pos >= len(data):
            return pos
        length = self._read_variable_length_item(pos, data)
        return pos + length

    def _skip_compound(self, pos: int, record: Record) -> int:
        """Skip compound item"""
        data = record.raw_data
        if pos >= len(data):
            return pos

        length = data[pos]
        return pos + length if pos + length <= len(data) else pos

    def _skip_repetitive(self, pos: int, record: Record) -> int:
        """Skip repetitive item (REP + data)"""
        data = record.raw_data
        if pos >= len(data):
            return pos

        rep = data[pos]
        item_size = 8
        total_length = 1 + (rep * item_size)

        return pos + total_length if pos + total_length <= len(data) else pos

    # ========== HELPER METHODS ==========

    def _read_variable_length_item(self, pos: int, data: bytes) -> int:
        """Read variable-length item with FX extension bit"""
        length = 0
        while pos + length < len(data):
            byte = data[pos + length]
            length += 1
            if not (byte & 0x01):
                break
        return length
