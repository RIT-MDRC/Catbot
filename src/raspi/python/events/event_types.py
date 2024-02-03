from enum import Enum

class EventType(Enum):
    """
    Represents all possible events that classes may need to subscribe to.
    """
    POTENTIOMETER_DATA_RECEIVED = 0
    PRESSURE_DATA_RECEIVED = 1
    MOTOR_STATUS_CHANGED = 2
    VALVE_STATUS_CHANGED = 3
    LIMIT_STATUS_CHANGED = 4
