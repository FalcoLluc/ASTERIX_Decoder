from enum import Enum, IntEnum


class CAT021ItemType(IntEnum):
    """ASTERIX Category 021 - ADS-B Reports"""

    # Items a decodificar
    DATA_SOURCE_IDENTIFICATION = 1  # I021/010 - 2 bytes
    TARGET_REPORT_DESCRIPTOR = 2  # I021/040 - Variable
    POSITION_WGS84_HIGH_RES = 7  # I021/131 - 8 bytes
    TARGET_ADDRESS = 11  # I021/080 - 3 bytes
    TIME_MESSAGE_RECEPTION_POSITION = 12  # I021/073 - 3 bytes
    MODE_3A_CODE = 19  # I021/070 - 2 bytes
    FLIGHT_LEVEL = 21  # I021/145 - 2 bytes
    TARGET_IDENTIFICATION = 29  # I021/170 - 6 bytes
    RESERVED_EXPANSION_FIELD = 48  # RE (BPS) - Variable

    # Items a saltar
    TRACK_NUMBER = 3  # I021/161 - 2 bytes
    SERVICE_IDENTIFICATION = 4  # I021/015 - 1 byte
    TIME_APPLICABILITY_POSITION = 5  # I021/071 - 3 bytes
    POSITION_WGS84 = 6  # I021/130 - 6 bytes
    TIME_APPLICABILITY_VELOCITY = 8  # I021/072 - 3 bytes
    AIR_SPEED = 9  # I021/150 - 2 bytes
    TRUE_AIRSPEED = 10  # I021/151 - 2 bytes
    TIME_MESSAGE_RECEPTION_POSITION_HIGH_PRECISION = 13  # I021/074 - 4 bytes
    TIME_MESSAGE_RECEPTION_VELOCITY = 14  # I021/075 - 3 bytes
    TIME_MESSAGE_RECEPTION_VELOCITY_HIGH_PRECISION = 15  # I021/076 - 4 bytes
    GEOMETRIC_HEIGHT = 16  # I021/140 - 2 bytes
    QUALITY_INDICATORS = 17  # I021/090 - Variable
    MOPS_VERSION = 18  # I021/210 - 1 byte
    ROLL_ANGLE = 20  # I021/230 - 2 bytes
    MAGNETIC_HEADING = 22  # I021/152 - 2 bytes
    TARGET_STATUS = 23  # I021/200 - 1 byte
    BAROMETRIC_VERTICAL_RATE = 24  # I021/155 - 2 bytes
    GEOMETRIC_VERTICAL_RATE = 25  # I021/157 - 2 bytes
    AIRBORNE_GROUND_VECTOR = 26  # I021/160 - 4 bytes
    TRACK_ANGLE_RATE = 27  # I021/165 - 2 bytes
    TIME_ASTERIX_REPORT_TRANSMISSION = 28  # I021/077 - 3 bytes
    EMITTER_CATEGORY = 30  # I021/020 - 1 byte
    MET_INFORMATION = 31  # I021/220 - Compound
    SELECTED_ALTITUDE = 32  # I021/146 - 2 bytes
    FINAL_STATE_SELECTED_ALTITUDE = 33  # I021/148 - 2 bytes
    TRAJECTORY_INTENT = 34  # I021/110 - Compound
    SERVICE_MANAGEMENT = 35  # I021/016 - 1 byte
    AIRCRAFT_OPERATIONAL_STATUS = 36  # I021/008 - 1 byte
    SURFACE_CAPABILITIES = 37  # I021/271 - Variable
    MESSAGE_AMPLITUDE = 38  # I021/132 - 1 byte
    MODE_S_MB_DATA = 39  # I021/250 - Repetitive
    ACAS_RESOLUTION_ADVISORY = 40  # I021/260 - 7 bytes
    RECEIVER_ID = 41  # I021/400 - 1 byte
    DATA_AGES = 42  # I021/295 - Compound
    SPECIAL_PURPOSE_FIELD = 49  # SP - Variable


class CAT048ItemType(IntEnum):
    """ASTERIX Category 048 - Monoradar Target Reports"""

    # METHODS TO DECODE
    DATA_SOURCE_IDENTIFIER = 1  # I048/010 - 2 bytes fixed
    TIME_OF_DAY = 2  # I048/140 - 3 bytes fixed
    TARGET_REPORT_DESCRIPTOR = 3  # I048/020 - Variable
    MEASURED_POSITION_POLAR = 4  # I048/040 - 4 bytes fixed
    MODE_3A_CODE = 5  # I048/070 - 2 bytes fixed
    FLIGHT_LEVEL = 6  # I048/090 - 2 bytes fixed
    RADAR_PLOT_CHARACTERISTICS = 7  # I048/130 - Compound (variable)
    AIRCRAFT_ADDRESS = 8  # I048/220 - 3 bytes fixed
    AIRCRAFT_IDENTIFICATION = 9  # I048/240 - 6 bytes fixed
    MODE_S_MB_DATA = 10  # I048/250 - Repetitive (variable)
    TRACK_NUMBER = 11  # I048/161 - 2 bytes fixed
    TRACK_VELOCITY_POLAR = 13  # I048/200 - 4 bytes fixed
    TRACK_STATUS = 14  # I048/170 - Variable
    COMMUNICATIONS_ACAS = 21  # I048/230 - 2 bytes fixed

    # METHODS TO SKIP
    CALCULATED_POSITION_CARTESIAN = 12  # I048/042 - 4 bytes fixed
    TRACK_QUALITY = 15  # I048/210 - 4 bytes fixed
    WARNING_ERROR_CONDITIONS = 16  # I048/030 - Variable
    MODE_3A_CONFIDENCE = 17  # I048/080 - 2 bytes fixed
    MODE_C_CODE_CONFIDENCE = 18  # I048/100 - 4 bytes fixed
    HEIGHT_3D_RADAR = 19  # I048/110 - 2 bytes fixed
    RADIAL_DOPPLER_SPEED = 20  # I048/120 - Compound (variable)


class Category(Enum):
    """ASTERIX Categories"""
    CAT021 = 21
    CAT048 = 48
