from enum import Enum

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


# Enum for CAT048 item types
class CAT048ItemType(Enum):
    TARGET_REPORT_DESCRIPTOR = 1
    TRACK_NUMBER = 2
    POSITION_CARTESIAN = 3
    POSITION_POLAR = 4
    VELOCITY_CARTESIAN = 5
    VELOCITY_POLAR = 6
    FLIGHT_LEVEL = 7
    MODE_3A_CODE = 8

class Category(Enum):
    CAT021 = 21
    CAT048 = 48