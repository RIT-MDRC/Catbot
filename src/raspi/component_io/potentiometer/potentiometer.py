class Potentiometer():
    """
    Represents a potentiometer that tracks the current abduction/adduction rotation
    of each leg.
    """
    pot_id : int
    reading : int = 0

    def __init__(self, pot_id : int) -> None:
        """
        Initialize a new instance of a potentiometer. There should only be
        one Potentiometer instance for each real-world potentiometer.

        :param pot_id: unique ID of the potentiometer [0-7]
        """
        self.pot_id = pot_id

    def get_position(self) -> float:
        """
        Gets the position (in degrees) for the potentiometer with this object's `pot_id`.
        Returns a non-zero value under normal operation; 0 if the potentiometer has hit a hardware
        limit.
        """
        return 0