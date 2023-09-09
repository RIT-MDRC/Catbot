from enum import Enum

class LimitStatus(Enum):
    """
    Represents whether a leg has reached its limit of range of motion on either axis.
    """
    NEGATIVE_LIMIT = -1
    NOT_AT_LIMIT = 0
    POSITIVE_LIMIT = 1

class Potentiometer():
    """
    Represents a potentiometer that tracks the current abduction/adduction rotation
    of each leg.
    """
    pot_id : int
    limit_status : LimitStatus = LimitStatus.NOT_AT_LIMIT
    last_read_value : int = 0

    def __init__(self, pot_id : int) -> None:
        """
        Initialize a new instance of a potentiometer. There should only be
        one Potentiometer instance for each real-world potentiometer.

        :param pot_id: unique ID of the potentiometer [0-7]
        """
        self.pot_id = pot_id

    # UML specifies get_id(), get_limit_status(), etc as getters for this class, but
    # in python all fields are public anyway so do we really need that?