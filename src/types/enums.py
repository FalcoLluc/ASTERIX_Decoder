from enum import Enum, IntEnum

class CAT021ItemType(Enum):
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
    DATA_SOURCE_IDENTIFIER = 1      # I048/010
    TIME_OF_DAY = 2                 # I048/140
    TARGET_REPORT_DESCRIPTOR = 3    # I048/020
    MEASURED_POSITION_POLAR = 4     # I048/040
    MODE_3A_CODE = 5                # I048/070
    FLIGHT_LEVEL = 6                # I048/090
    RADAR_PLOT_CHARACTERISTICS = 7  # I048/130
    AIRCRAFT_ADDRESS = 8            # I048/220
    AIRCRAFT_IDENTIFICATION = 9     # I048/240
    MODE_S_MB_DATA = 10             # I048/250
    TRACK_NUMBER = 11               # I048/161
    TRACK_VELOCITY_POLAR = 13       # I048/200
    TRACK_STATUS = 14               # I048/170
    COMMUNICATIONS_ACAS = 21        # I048/230

class Category(Enum):
    CAT021 = 21
    CAT048 = 48