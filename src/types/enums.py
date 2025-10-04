from enum import Enum, IntEnum

class CAT021ItemType(IntEnum):
    TARGET_REPORT_DESCRIPTOR = 1
    TRACK_NUMBER = 2
    POSITION_WGS84 = 3
    POSITION_CARTESIAN = 4
    VELOCITY_CARTESIAN = 5
    VELOCITY_POLAR = 6
    CALLSIGN = 7
    TIME_OF_DAY = 8
    # Add more CAT021 item types as needed

class CAT048ItemType(IntEnum):
    # METHODS TO DECODE
    DATA_SOURCE_IDENTIFIER = 1      # I048/010 - 2 bytes fixed
    TIME_OF_DAY = 2                 # I048/140 - 3 bytes fixed
    TARGET_REPORT_DESCRIPTOR = 3    # I048/020 - Variable
    MEASURED_POSITION_POLAR = 4     # I048/040 - 4 bytes fixed
    MODE_3A_CODE = 5                # I048/070 - 2 bytes fixed
    FLIGHT_LEVEL = 6                # I048/090 - 2 bytes fixed
    RADAR_PLOT_CHARACTERISTICS = 7  # I048/130 - Compound (variable)
    AIRCRAFT_ADDRESS = 8            # I048/220 - 3 bytes fixed
    AIRCRAFT_IDENTIFICATION = 9     # I048/240 - 6 bytes fixed
    MODE_S_MB_DATA = 10             # I048/250 - Repetitive (variable)
    TRACK_NUMBER = 11               # I048/161 - 2 bytes fixed
    TRACK_VELOCITY_POLAR = 13       # I048/200 - 4 bytes fixed
    TRACK_STATUS = 14               # I048/170 - Variable
    COMMUNICATIONS_ACAS = 21        # I048/230 - 2 bytes fixed

    # METHODS TO SKIP
    CALCULATED_POSITION_CARTESIAN = 12  # I048/042 - 4 bytes fixed
    TRACK_QUALITY = 15              # I048/210 - 4 bytes fixed
    WARNING_ERROR_CONDITIONS = 16   # I048/030 - Variable
    MODE_3A_CONFIDENCE = 17         # I048/080 - 2 bytes fixed
    MODE_C_CODE_CONFIDENCE = 18     # I048/100 - 4 bytes fixed
    HEIGHT_3D_RADAR = 19            # I048/110 - 2 bytes fixed
    RADIAL_DOPPLER_SPEED = 20       # I048/120 - Compound (variable)
    # FRN 22-28 not needed - decoding stops at FRN 21

class Category(Enum):
    CAT021 = 21
    CAT048 = 48