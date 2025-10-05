from src.decoders.asterix_decoder_base import AsterixDecoderBase
from src.types.enums import CAT048ItemType
from src.models.record import Record
from src.models.item import Item
from typing import List

"""
Dentro del DI I048/250 “Mode S MB Data” solo hará falta decodificar los subcampos de los
BDS 4.0, 5.0, 6.0
"""

class Cat048Decoder(AsterixDecoderBase):
    def __init__(self):
        super().__init__()
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
            CAT048ItemType.CALCULATED_POSITION_CARTESIAN: self._skip_calculated_position_cartesian,
            CAT048ItemType.TRACK_VELOCITY_POLAR: self._decode_track_velocity_polar,
            CAT048ItemType.TRACK_STATUS: self._decode_track_status,
            CAT048ItemType.TRACK_QUALITY: self._skip_track_quality,
            CAT048ItemType.WARNING_ERROR_CONDITIONS: self._skip_warning_error_conditions,
            CAT048ItemType.MODE_3A_CONFIDENCE: self._skip_mode_3a_confidence,
            CAT048ItemType.MODE_C_CODE_CONFIDENCE: self._skip_mode_c_code_confidence,
            CAT048ItemType.HEIGHT_3D_RADAR: self._skip_height_3d_radar,
            CAT048ItemType.RADIAL_DOPPLER_SPEED: self._skip_radial_doppler_speed,
            CAT048ItemType.COMMUNICATIONS_ACAS: self._decode_communications_acas,
        }

    def decode_record(self, record: Record) -> Record:
        """Main decoding method"""
        # Parse FSPEC to get list of items in order
        self.logger.debug("Starting decode_record: offset=%s, raw_len=%s", getattr(record, 'block_offset', None), len(record.raw_data))
        fspec_items, data_start = self._parse_fspec(record)
        self.logger.debug("Parsed FSPEC: %d items, data_start=%d", len(fspec_items), data_start)

        # Initialize pointer to data after FSPEC
        data_pointer = data_start

        # Decode each item in FSPEC order
        for item_type in fspec_items:
            decoder_func = self.decoder_map.get(item_type)
            if decoder_func:
                # Each decoder returns the new data pointer position
                data_pointer = decoder_func(data_pointer, record)
            else:
                self.logger.warning("No decoder for CAT048 item %s", item_type)
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
                        # FRN not in our enum (e.g., FRN 22-28)
                        # Although they do not need to be decoded, we have to compute start position!
                        # We'll handle this by stopping at FRN 21
                        pass

                # frn will always be increasing, but only when AND is successful, an item is added
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

        item = Item(
            item_offset=pos,
            length=3,
            frn=2,
            item_type=CAT048ItemType.TIME_OF_DAY,
            value={
                "total_seconds": total_seconds,
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds
            }
        )
        record.items.append(item)

        return pos + 3

    def _decode_target_report_descriptor(self, pos: int, record: Record) -> int:
        """I048/020 - Target Report Descriptor (Variable length)"""
        data = record.raw_data
        if pos >= len(data):
            return pos

        # Variable length item - read until FX bit is 0
        length = self._read_variable_length_item(pos, data)

        # Decode the first octet
        first_octet = data[pos]

        typ = (first_octet >> 5) & 0x07  # bits 8-6
        sim = (first_octet >> 4) & 0x01  # bit 5
        rdp = (first_octet >> 3) & 0x01  # bit 4
        spi = (first_octet >> 2) & 0x01  # bit 3
        rab = (first_octet >> 1) & 0x01  # bit 2

        value = {
            "TYP": typ,  # 0=No detection, 1=PSR, 2=SSR, 3=SSR+PSR, 4=ModeS All-Call, etc.
            "SIM": sim,  # 0=Actual, 1=Simulated
            "RDP": rdp,  # 0=RDP Chain 1, 1=RDP Chain 2
            "SPI": spi,  # 0=No SPI, 1=Special Position Identification
            "RAB": rab  # 0=Aircraft transponder, 1=Field monitor
        }

        # Decode first extension if present (FX bit set in first octet)
        if length >= 2 and (first_octet & 0x01):
            second_octet = data[pos + 1]
            value["TST"] = (second_octet >> 7) & 0x01  # Real=0, Test=1
            value["ERR"] = (second_octet >> 6) & 0x01  # Extended Range
            value["XPP"] = (second_octet >> 5) & 0x01  # X-Pulse present
            value["ME"] = (second_octet >> 4) & 0x01  # Military emergency
            value["MI"] = (second_octet >> 3) & 0x01  # Military identification
            value["FOEFRI"] = (second_octet >> 1) & 0x03  # IFF Mode 4

        # Decode second extension if present (added in v1.31)
        if length >= 3 and (data[pos + 1] & 0x01):
            third_octet = data[pos + 2]
            value["ADSB"] = (third_octet >> 6) & 0x03  # ADS-B info (2 bits)
            value["SCN"] = (third_octet >> 4) & 0x03  # Surveillance Cluster Network (2 bits)
            value["PAI"] = (third_octet >> 2) & 0x03  # Passive Acquisition Interface (2 bits)

        item = Item(
            item_offset=pos,
            length=length,
            frn=3,
            item_type=CAT048ItemType.TARGET_REPORT_DESCRIPTOR,
            value=value
        )
        record.items.append(item)

        return pos + length

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
                "RHO_nm": range_nm,
                "THETA_degrees": theta_degrees,
            }
        )

        record.items.append(item)
        return pos + 4

    def _decode_mode_3a_code(self, pos: int, record: Record) -> int:
        """I048/070 - Mode-3/A Code in Octal Representation (2 bytes fixed)"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        # Read 2 bytes
        byte1 = data[pos]
        byte2 = data[pos + 1]

        # Extract V, G, L flags from first byte
        v = (byte1 >> 7) & 0x01  # bit 16: V - Validated
        g = (byte1 >> 6) & 0x01  # bit 15: G - Garbled
        l = (byte1 >> 5) & 0x01  # bit 14: L - Derived from reply or smoothed
        # bit 13 is spare (bit 4 of byte1)

        # Extract Mode-3/A code (12 bits in octal representation)
        # Bits 12-1: A4 A2 A1 B4 B2 B1 C4 C2 C1 D4 D2 D1
        mode_3a_raw = ((byte1 & 0x0F) << 8) | byte2  # 12 bits

        # Extract individual octal digits (each digit is 3 bits)
        a = (mode_3a_raw >> 9) & 0x07  # bits 12-10
        b = (mode_3a_raw >> 6) & 0x07  # bits 9-7
        c = (mode_3a_raw >> 3) & 0x07  # bits 6-4
        d = mode_3a_raw & 0x07  # bits 3-1

        # Convert to octal string representation (ABCD)
        mode_3a_octal = f"{a}{b}{c}{d}"

        item = Item(
            item_offset=pos,
            length=2,
            frn=5,
            item_type=CAT048ItemType.MODE_3A_CODE,
            value={
                "V": v,  # 0=validated, 1=not validated
                "G": g,  # 0=default, 1=garbled
                "L": l,  # 0=derived from transponder, 1=smoothed/not extracted
                "Mode3/A": mode_3a_octal,
                "A": a,
                "B": b,
                "C": c,
                "D": d
            }
        )
        record.items.append(item)

        return pos + 2

    def _decode_flight_level(self, pos: int, record: Record) -> int:
        """I048/090 - Flight Level in Binary Representation (2 bytes fixed)"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        # Read 2 bytes
        byte1 = data[pos]
        byte2 = data[pos + 1]

        # Extract V and G flags from first byte
        v = (byte1 >> 7) & 0x01  # bit 16: V - Validated
        g = (byte1 >> 6) & 0x01  # bit 15: G - Garbled

        # Extract Flight Level (14 bits) - bits 14-1
        # Mask out V and G bits, combine with second byte
        flight_level_raw = ((byte1 & 0x3F) << 8) | byte2

        # Convert to signed value (two's complement for 14 bits)
        if flight_level_raw & 0x2000:  # Check if bit 13 (sign bit) is set
            flight_level = flight_level_raw - 0x4000  # Convert from 14-bit two's complement
        else:
            flight_level = flight_level_raw

        # Calculate flight level in units (LSB = 1/4 FL)
        flight_level_value = flight_level / 4.0

        item = Item(
            item_offset=pos,
            length=2,
            frn=6,
            item_type=CAT048ItemType.FLIGHT_LEVEL,
            value={
                "V": v,  # 0=validated, 1=not validated
                "G": g,  # 0=default, 1=garbled
                "FL": flight_level_value,  # In Flight Level units (hundreds of feet)
                "altitude_feet": flight_level_value * 100  # Convert FL to feet
            }
        )
        record.items.append(item)

        return pos + 2

    def _decode_radar_plot_characteristics(self, pos: int, record: Record) -> int:
        """I048/130 - Radar Plot Characteristics (Compound, variable length)"""
        data = record.raw_data
        if pos >= len(data):
            return pos

        # Read the compound item length using the helper
        length = self._read_compound_length(pos, data)

        # Read primary subfield to determine which subfields are present
        primary_byte = data[pos]
        current_pos = pos + 1  # Start after primary subfield

        value = {}

        # Bit 8: SRL - SSR plot runlength
        if primary_byte & 0x80 and current_pos < pos + length:
            srl = data[current_pos]
            value["SRL"] = srl * (360.0 / (2 ** 13))  # LSB = 360°/2^13 ≈ 0.044°
            current_pos += 1

        # Bit 7: SRR - Number of received replies for MSSR
        if primary_byte & 0x40 and current_pos < pos + length:
            value["SRR"] = data[current_pos]  # Number of replies
            current_pos += 1

        # Bit 6: SAM - Amplitude of MSSR reply
        if primary_byte & 0x20 and current_pos < pos + length:
            sam = data[current_pos]
            # Signed value in two's complement
            if sam & 0x80:
                sam = sam - 256
            value["SAM"] = sam  # In dBm
            current_pos += 1

        # Bit 5: PRL - PSR plot runlength
        if primary_byte & 0x10 and current_pos < pos + length:
            prl = data[current_pos]
            value["PRL"] = prl * (360.0 / (2 ** 13))  # LSB = 360°/2^13 ≈ 0.044°
            current_pos += 1

        # Bit 4: PAM - PSR amplitude
        if primary_byte & 0x08 and current_pos < pos + length:
            pam = data[current_pos]
            # Signed value in two's complement
            if pam & 0x80:
                pam = pam - 256
            value["PAM"] = pam  # In dBm
            current_pos += 1

        # Bit 3: RPD - Difference in Range between PSR and SSR
        if primary_byte & 0x04 and current_pos < pos + length:
            rpd = data[current_pos]
            # Signed value in two's complement
            if rpd & 0x80:
                rpd = rpd - 256
            value["RPD"] = rpd / 256.0  # LSB = 1/256 NM
            current_pos += 1

        # Bit 2: APD - Difference in Azimuth between PSR and SSR
        if primary_byte & 0x02 and current_pos < pos + length:
            apd = data[current_pos]
            # Signed value in two's complement
            if apd & 0x80:
                apd = apd - 256
            value["APD"] = apd * (360.0 / (2 ** 14))  # LSB = 360°/2^14
            current_pos += 1

        item = Item(
            item_offset=pos,
            length=length,
            frn=7,
            item_type=CAT048ItemType.RADAR_PLOT_CHARACTERISTICS,
            value=value
        )
        record.items.append(item)

        return pos + length

    def _decode_aircraft_address(self, pos: int, record: Record) -> int:
        """I048/220 - Aircraft Address (3 bytes fixed)
        24-bit Mode S address (ICAO 24-bit aircraft address)
        """
        data = record.raw_data
        if pos + 3 > len(data):
            return pos

        # Read 3 bytes - Mode S address (A23 to A0)
        address_bytes = data[pos:pos + 3]
        aircraft_address = int.from_bytes(address_bytes, byteorder='big')

        # Convert to hexadecimal representation (standard format for Mode S addresses)
        aircraft_address_hex = f"{aircraft_address:06X}"

        item = Item(
            item_offset=pos,
            length=3,
            frn=8,
            item_type=CAT048ItemType.AIRCRAFT_ADDRESS,
            value={
                "aircraft_address": aircraft_address,
                "aircraft_address_hex": aircraft_address_hex,
            }
        )
        record.items.append(item)

        return pos + 3

    def _decode_aircraft_identification(self, pos: int, record: Record) -> int:
        """I048/240 - Aircraft Identification (6 bytes fixed)
        Target identification in 8 characters, as reported by Mode S transponder
        """
        data = record.raw_data
        if pos + 6 > len(data):
            return pos

        # Read 6 bytes (48 bits) containing 8 characters of 6 bits each
        id_bytes = data[pos:pos + 6]

        # Convert bytes to 48-bit integer
        id_value = int.from_bytes(id_bytes, byteorder='big')

        # Extract 8 characters (6 bits each)
        callsign = ""
        for i in range(8):
            # Extract 6 bits for each character (from MSB to LSB)
            shift = 42 - (i * 6)  # 42, 36, 30, 24, 18, 12, 6, 0
            char_code = (id_value >> shift) & 0x3F  # 0x3F = 63 (6 bits mask)

            # Convert IA5 6-bit code to ASCII character
            # According to ICAO Annex 10, the encoding is:
            # 1-26: A-Z, 32: space, 48-57: 0-9
            if 1 <= char_code <= 26:
                char = chr(ord('A') + char_code - 1)
            elif char_code == 32:
                char = ' '
            elif 48 <= char_code <= 57:
                char = chr(char_code)
            else:
                char = ' '  # Invalid character, use space

            callsign += char

        # Remove trailing spaces
        callsign = callsign.rstrip()

        item = Item(
            item_offset=pos,
            length=6,
            frn=9,
            item_type=CAT048ItemType.AIRCRAFT_IDENTIFICATION,
            value={
                "TI": callsign,
            }
        )
        record.items.append(item)

        return pos + 6

    def _decode_mode_s_mb_data(self, pos: int, record: Record) -> int:
        """I048/250 - Mode S MB Data (Repetitive, variable length)
        BDS Register Data - decode only BDS 4.0, 5.0, 6.0
        """
        data = record.raw_data
        if pos >= len(data):
            return pos

        # First byte is REP (repetition factor)
        if pos + 1 > len(data):
            return pos

        rep = data[pos]
        # Each BDS register is 8 bytes (7 bytes data + 1 byte BDS code)
        item_size = 8
        total_length = 1 + (rep * item_size)

        if pos + total_length > len(data):
            return pos

        # Decode each BDS register
        bds_registers = []
        current_pos = pos + 1  # Start after REP byte

        for i in range(rep):
            if current_pos + 8 > len(data):
                break

            # Read 7 bytes of BDS data
            bds_data = data[current_pos:current_pos + 7]
            # Read 1 byte of BDS code
            bds_code = data[current_pos + 7]

            # Extract BDS1 and BDS2 (4 bits each)
            bds1 = (bds_code >> 4) & 0x0F
            bds2 = bds_code & 0x0F

            bds_register = {
                "bds_code": f"{bds1}{bds2}",
                "bds1": bds1,
                "bds2": bds2,
            }

            # Decode specific BDS registers
            if bds1 == 4 and bds2 == 0:
                # BDS 4.0 - Selected vertical intention
                bds_register.update(self._decode_bds_40(bds_data))
            elif bds1 == 5 and bds2 == 0:
                # BDS 5.0 - Track and turn report
                bds_register.update(self._decode_bds_50(bds_data))
            elif bds1 == 6 and bds2 == 0:
                # BDS 6.0 - Heading and speed report
                bds_register.update(self._decode_bds_60(bds_data))

            bds_registers.append(bds_register)
            current_pos += 8

        item = Item(
            item_offset=pos,
            length=total_length,
            frn=10,
            item_type=CAT048ItemType.MODE_S_MB_DATA,
            value={
                "rep": rep,
                "bds_registers": bds_registers
            }
        )
        record.items.append(item)

        return pos + total_length

    def _decode_bds_40(self, bds_data: bytes) -> dict:
        """Decode BDS 4.0 - Selected vertical intention"""
        result = {}

        # Convert to 56-bit integer
        bds_value = int.from_bytes(bds_data, byteorder='big')

        # MCP/FCU Selected Altitude (bits 56-44, 13 bits)
        mcp_fcu_status = (bds_value >> 55) & 0x01
        if mcp_fcu_status:
            mcp_fcu_alt_raw = (bds_value >> 43) & 0x0FFF  # 12 bits
            mcp_fcu_alt = mcp_fcu_alt_raw * 16  # LSB = 16 ft
            result["MCP_FCU_ALT_ft"] = mcp_fcu_alt

        # FMS Selected Altitude (bits 43-31, 13 bits)
        fms_status = (bds_value >> 42) & 0x01
        if fms_status:
            fms_alt_raw = (bds_value >> 30) & 0x0FFF  # 12 bits
            fms_alt = fms_alt_raw * 16  # LSB = 16 ft
            result["FMS_ALT_ft"] = fms_alt

        # Barometric Pressure Setting (bits 30-18, 13 bits)
        baro_status = (bds_value >> 29) & 0x01
        if baro_status:
            baro_raw = (bds_value >> 17) & 0x0FFF  # 12 bits
            baro_setting = baro_raw * 0.1 + 800  # LSB = 0.1 mb, offset 800 mb
            result["BP_mb"] = baro_setting

        return result

    def _decode_bds_50(self, bds_data: bytes) -> dict:
        """Decode BDS 5.0 - Track and turn report"""
        result = {}

        # Convert to 56-bit integer
        bds_value = int.from_bytes(bds_data, byteorder='big')

        # Roll Angle (bits 1-11: status + sign + 9 data)
        roll_status = (bds_value >> 55) & 0x01  # bit 56 (actual bit 1)
        if roll_status:
            roll_raw = (bds_value >> 45) & 0x03FF  # bits 55-46 (actual bits 2-11: sign + 9 data)
            if roll_raw & 0x0200:  # Check sign bit (10-bit field)
                roll_raw = roll_raw - 0x0400
            roll_angle = roll_raw * 45.0 / 256.0
            result["RA_deg"] = roll_angle

        # True Track Angle (bits 12-23: status + sign + 10 data) - 12 bits total!
        track_status = (bds_value >> 44) & 0x01  # bit 45 (actual bit 12)
        if track_status:
            track_raw = (bds_value >> 33) & 0x07FF  # bits 44-34 (actual bits 13-23: sign + 10 data) - FIXED to 11 bits!
            if track_raw & 0x0400:  # Check sign bit (11-bit field)
                track_raw = track_raw - 0x0800  # Two's complement for 11 bits
            track_angle = track_raw * 90.0 / 512.0
            result["TTA_deg"] = track_angle

        # Ground Speed (bits 24-34: status + 10 data)
        gs_status = (bds_value >> 32) & 0x01  # bit 33 (actual bit 24) - FIXED
        if gs_status:
            gs_raw = (bds_value >> 22) & 0x03FF  # bits 32-23 (actual bits 25-34: 10 data) - FIXED
            ground_speed = gs_raw * 2
            result["GS_kt"] = ground_speed

        # Track Angle Rate (bits 35-45: status + sign + 9 data)
        tar_status = (bds_value >> 21) & 0x01  # bit 22 (actual bit 35) - FIXED
        if tar_status:
            tar_raw = (bds_value >> 11) & 0x03FF  # bits 21-12 (actual bits 36-45: sign + 9 data) - FIXED to 10 bits!
            if tar_raw & 0x0200:  # Check sign bit (10-bit field)
                tar_raw = tar_raw - 0x0400
            track_rate = tar_raw * 8.0 / 256.0
            result["TAR_deg_s"] = track_rate

        # True Airspeed (bits 46-56: status + 10 data)
        tas_status = (bds_value >> 10) & 0x01  # bit 11 (actual bit 46) - FIXED
        if tas_status:
            tas_raw = (bds_value >> 0) & 0x03FF  # bits 10-1 (actual bits 47-56: 10 data) - FIXED
            true_airspeed = tas_raw * 2
            result["TAS_kt"] = true_airspeed

        return result

    def _decode_bds_60(self, bds_data: bytes) -> dict:
        """Decode BDS 6.0 - Heading and speed report"""
        result = {}

        # Convert to 56-bit integer (bit 56 = MSB at shift position 55, bit 1 = LSB at position 0)
        bds_value = int.from_bytes(bds_data, byteorder='big')

        # Magnetic Heading (bits 1-12: status + sign + 10 data)
        mag_heading_status = (bds_value >> 55) & 0x01  # bit 56 (actual bit 1)
        if mag_heading_status:
            mag_heading_raw = (bds_value >> 45) & 0x07FF  # bits 55-45 (actual bits 2-12: sign + 10 data)
            # Check sign bit (bit 55 = actual bit 2)
            if mag_heading_raw & 0x0400:  # bit 10 of the 11-bit field
                mag_heading_raw = mag_heading_raw - 0x0800  # Convert from 11-bit two's complement
            mag_heading = mag_heading_raw * 90.0 / 512.0  # LSB = 90/512 degrees
            result["MG_HDG_deg"] = mag_heading

        # Indicated Airspeed (bits 13-23: status + 10 data)
        ias_status = (bds_value >> 43) & 0x01  # bit 44 (actual bit 13)
        if ias_status:
            ias_raw = (bds_value >> 33) & 0x03FF  # bits 43-34 (actual bits 14-23: 10 data bits)
            indicated_airspeed = ias_raw  # LSB = 1 knot
            result["IAS_kt"] = indicated_airspeed

        # Mach Number (bits 24-34: status + 10 data)
        mach_status = (bds_value >> 32) & 0x01  # bit 33 (actual bit 24)
        if mach_status:
            mach_raw = (bds_value >> 22) & 0x03FF  # bits 32-23 (actual bits 25-34: 10 data bits)
            mach_number = mach_raw * (2.048 / 512.0)  # LSB = 2.048/512 = 0.004
            result["MACH"] = mach_number

        # Barometric Altitude Rate (bits 35-45: status + sign + 9 data)
        baro_rate_status = (bds_value >> 21) & 0x01  # bit 22 (actual bit 35)
        if baro_rate_status:
            baro_rate_raw = (bds_value >> 11) & 0x03FF  # bits 21-12 (actual bits 36-45: sign + 9 data)
            # Check sign bit (bit 21 = actual bit 36)
            if baro_rate_raw & 0x0200:  # bit 9 of the 10-bit field
                baro_rate_raw = baro_rate_raw - 0x0400  # Convert from 10-bit two's complement
            baro_rate = baro_rate_raw * 32  # LSB = 32 ft/min
            result["BAR_RATE_ft_min"] = baro_rate

        # Inertial Vertical Velocity (bits 46-56: status + sign + 9 data)
        ivv_status = (bds_value >> 10) & 0x01  # bit 11 (actual bit 46)
        if ivv_status:
            ivv_raw = (bds_value >> 0) & 0x03FF  # bits 10-1 (actual bits 47-56: sign + 9 data)
            # Check sign bit (bit 10 = actual bit 47)
            if ivv_raw & 0x0200:  # bit 9 of the 10-bit field
                ivv_raw = ivv_raw - 0x0400  # Convert from 10-bit two's complement
            inertial_vv = ivv_raw * 32  # LSB = 32 ft/min
            result["IVV_ft_min"] = inertial_vv

        return result

    def _decode_track_number(self, pos: int, record: Record) -> int:
        """I048/161 - Track Number (2 bytes fixed)
        An integer value representing a unique reference to a track record
        """
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        # Read 2 bytes
        # Bits 16-13 are spare (set to 0)
        # Bits 12-1 contain the track number (0-4095)
        track_number_raw = int.from_bytes(data[pos:pos + 2], byteorder='big')
        track_number = track_number_raw & 0x0FFF  # Mask to get bits 12-1 (12 bits = 0x0FFF)

        item = Item(
            item_offset=pos,
            length=2,
            frn=11,
            item_type=CAT048ItemType.TRACK_NUMBER,
            value={"TN": track_number}
        )
        record.items.append(item)

        return pos + 2

    def _decode_track_velocity_polar(self, pos: int, record: Record) -> int:
        """I048/200 - Calculated Track Velocity in Polar Representation (4 bytes fixed)
        Calculated track velocity expressed in polar coordinates
        """
        data = record.raw_data
        if pos + 4 > len(data):
            return pos

        # Read 4 bytes
        velocity_bytes = data[pos:pos + 4]

        # Extract Calculated Ground Speed - first 2 bytes (16 bits)
        speed_raw = int.from_bytes(velocity_bytes[0:2], byteorder='big')

        # Extract Calculated Heading - last 2 bytes (16 bits)
        heading_raw = int.from_bytes(velocity_bytes[2:4], byteorder='big')

        # Convert Ground Speed (LSB = 2^-14 NM/s ≈ 0.22 kt)
        ground_speed_kt = speed_raw * (2 ** -14) * 3600  # Convert NM/s to knots

        # Convert Heading to degrees (LSB = 360°/2^16 ≈ 0.0055°)
        heading_degrees = (heading_raw * 360.0) / 65536.0

        # Normalize heading to 0-360 degrees
        heading_degrees %= 360.0

        item = Item(
            item_offset=pos,
            length=4,
            frn=13,
            item_type=CAT048ItemType.TRACK_VELOCITY_POLAR,
            value={
                "GS_kt": ground_speed_kt,
                "HDG_degrees": heading_degrees,
            }
        )
        record.items.append(item)

        return pos + 4

    def _decode_track_status(self, pos: int, record: Record) -> int:
        """I048/170 - Track Status (Variable length)
        Status of monoradar track (PSR and/or SSR updated)
        """
        data = record.raw_data
        if pos >= len(data):
            return pos

        # Variable length item - read until FX bit is 0
        length = self._read_variable_length_item(pos, data)

        # Decode first octet
        first_octet = data[pos]

        cnf = (first_octet >> 7) & 0x01  # bit 8
        rad = (first_octet >> 5) & 0x03  # bits 7-6
        dou = (first_octet >> 4) & 0x01  # bit 5
        mah = (first_octet >> 3) & 0x01  # bit 4
        cdm = (first_octet >> 1) & 0x03  # bits 3-2

        value = {
            "CNF": cnf,  # 0=Confirmed track, 1=Tentative track
            "RAD": rad,  # 0=Combined, 1=PSR, 2=SSR/Mode S, 3=Invalid
            "DOU": dou,  # 0=Normal confidence, 1=Low confidence
            "MAH": mah,  # 0=No horizontal maneuver, 1=Horizontal maneuver sensed
            "CDM": cdm  # 0=Maintaining, 1=Climbing, 2=Descending, 3=Unknown
        }

        # Decode first extension if present
        if length >= 2 and (first_octet & 0x01):
            second_octet = data[pos + 1]
            value["TRE"] = (second_octet >> 7) & 0x01  # Track still alive=0, End of track=1
            value["GHO"] = (second_octet >> 6) & 0x01  # True target=0, Ghost=1
            value["SUP"] = (second_octet >> 5) & 0x01  # Track maintained with neighbor info
            value["TCC"] = (second_octet >> 4) & 0x01  # 0=Radar plane, 1=2D projection

        item = Item(
            item_offset=pos,
            length=length,
            frn=14,
            item_type=CAT048ItemType.TRACK_STATUS,
            value=value
        )
        record.items.append(item)

        return pos + length

    def _decode_communications_acas(self, pos: int, record: Record) -> int:
        """I048/230 - Communications/ACAS Capability and Flight Status (2 bytes fixed)
        Communications capability of the transponder, ACAS equipment capability, and flight status
        """
        data = record.raw_data
        if pos + 2 > len(data):
            return pos

        # Read 2 bytes
        byte1 = data[pos]
        byte2 = data[pos + 1]

        # Extract fields from first byte (bits 16-9)
        com = (byte1 >> 5) & 0x07  # bits 16-14: COM (3 bits)
        stat = (byte1 >> 2) & 0x07  # bits 13-11: STAT (3 bits)
        si = (byte1 >> 1) & 0x01  # bit 10: SI
        # bit 9 is spare

        # Extract fields from second byte (bits 8-1)
        mssc = (byte2 >> 7) & 0x01  # bit 8: MSSC
        arc = (byte2 >> 6) & 0x01  # bit 7: ARC
        aic = (byte2 >> 5) & 0x01  # bit 6: AIC
        b1a = (byte2 >> 4) & 0x01  # bit 5: B1A
        b1b = byte2 & 0x0F  # bits 4-1: B1B (4 bits)

        # COM values mapping
        com_mapping = {
            0: "No communications capability (surveillance only)",
            1: "Comm. A and Comm. B capability",
            2: "Comm. A, Comm. B and Uplink ELM",
            3: "Comm. A, Comm. B, Uplink ELM and Downlink ELM",
            4: "Level 5 Transponder capability",
            5: "Not assigned",
            6: "Not assigned",
            7: "Not assigned"
        }

        # STAT values mapping
        stat_mapping = {
            0: "No alert, no SPI, aircraft airborne",
            1: "No alert, no SPI, aircraft on ground",
            2: "Alert, no SPI, aircraft airborne",
            3: "Alert, no SPI, aircraft on ground",
            4: "Alert, SPI, aircraft airborne or on ground",
            5: "No alert, SPI, aircraft airborne or on ground",
            6: "Not assigned",
            7: "Unknown"
        }

        item = Item(
            item_offset=pos,
            length=2,
            frn=21,
            item_type=CAT048ItemType.COMMUNICATIONS_ACAS,
            value={
                "COM": com,
                "COM_description": com_mapping.get(com, "Unknown"),
                "STAT": stat,
                "STAT_description": stat_mapping.get(stat, "Unknown"),
                "SI": si,  # 0=SI-Code Capable, 1=II-Code Capable
                "MSSC": mssc,  # Mode-S Specific Service Capability: 0=No, 1=Yes
                "ARC": arc,  # Altitude reporting: 0=100ft resolution, 1=25ft resolution
                "AIC": aic,  # Aircraft identification capability: 0=No, 1=Yes
                "B1A": b1a,  # BDS 1,0 bit 16
                "B1B": b1b  # BDS 1,0 bits 37-40
            }
        )
        record.items.append(item)

        return pos + 2

    # METHODS TO SKIP ITEMS
    def _skip_calculated_position_cartesian(self, pos: int, record: Record) -> int:
        """I048/042 - Calculated Position in Cartesian Coordinates (4 bytes fixed) - SKIP"""
        data = record.raw_data
        if pos + 4 > len(data):
            return pos
        return pos + 4

    def _skip_track_quality(self, pos: int, record: Record) -> int:
        """I048/210 - Track Quality (4 bytes fixed) - SKIP"""
        data = record.raw_data
        if pos + 4 > len(data):
            return pos
        return pos + 4

    def _skip_warning_error_conditions(self, pos: int, record: Record) -> int:
        """I048/030 - Warning/Error Conditions (variable length) - SKIP"""
        data = record.raw_data
        if pos >= len(data):
            return pos
        length = self._read_variable_length_item(pos, data)
        return pos + length

    def _skip_mode_3a_confidence(self, pos: int, record: Record) -> int:
        """I048/080 - Mode-3/A Code Confidence Indicator (2 bytes fixed) - SKIP"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos
        return pos + 2

    def _skip_mode_c_code_confidence(self, pos: int, record: Record) -> int:
        """I048/100 - Mode-C Code and Confidence Indicator (4 bytes fixed) - SKIP"""
        data = record.raw_data
        if pos + 4 > len(data):
            return pos
        return pos + 4

    def _skip_height_3d_radar(self, pos: int, record: Record) -> int:
        """I048/110 - Height Measured by 3D Radar (2 bytes fixed) - SKIP"""
        data = record.raw_data
        if pos + 2 > len(data):
            return pos
        return pos + 2

    def _skip_radial_doppler_speed(self, pos: int, record: Record) -> int:
        """I048/120 - Radial Doppler Speed (compound, variable) - SKIP"""
        data = record.raw_data
        if pos >= len(data):
            return pos
        length = self._read_compound_length(pos, data)
        return pos + length

    # ========== HELPER METHODS ==========
    def _read_variable_length_item(self, pos: int, data: bytes) -> int:
        """Read variable-length item with FX extension bit."""
        length = 0
        while pos + length < len(data):
            byte = data[pos + length]
            length += 1
            if not (byte & 0x01):  # FX bit is 0
                break
        return length

    def _read_compound_length(self, pos: int, data: bytes) -> int:
        """
        Read compound item length by examining primary subfield.
        Returns total length in bytes (primary subfield + data subfields).
        """
        if pos >= len(data):
            return 0

        # For I048/130, primary subfield is 1 byte (non-extensible)
        # Bit 1 is always FX=0 for this item
        primary_byte = data[pos]
        total_length = 1  # Start with 1 byte for primary subfield

        # Count how many subfields are present by checking bits 7-2
        # Bit 8 (0x80) = SRL present
        # Bit 7 (0x40) = SRR present
        # Bit 6 (0x20) = SAM present
        # Bit 5 (0x10) = PRL present
        # Bit 4 (0x08) = PAM present
        # Bit 3 (0x04) = RPD present
        # Bit 2 (0x02) = APD present
        # Bit 1 (0x01) = FX (should be 0 for I048/130)

        for bit in range(7, 0, -1):  # Check bits 8-2 (skip bit 1 which is FX)
            if primary_byte & (1 << bit):
                total_length += 1  # Each subfield is 1 byte

        return total_length

    def _read_repetitive_length(self, pos: int, data: bytes) -> int:
        """Read repetitive item length (REP + data)."""
        if pos >= len(data):
            return 0

        rep = data[pos]
        item_size = 8  # For I048/250, each repetition is 8 bytes
        return 1 + (rep * item_size)
