from enum import Enum

class LimitStatus(Enum):
    NEGATIVE_LIMIT = -1
    NOT_AT_LIMIT = 0
    POSITIVE_LIMIT = 1

class Potentiometer():
    pot_id : int
    limit_status : LimitStatus = LimitStatus.NOT_AT_LIMIT
    last_read_value : int = 0

    def __init__(self, pot_id) -> None:
        self.pot_id = pot_id

    # UML specifies get_id(), get_limit_status(), etc as getters for this class, but
    # in python all fields are public anyway so do we really need that?