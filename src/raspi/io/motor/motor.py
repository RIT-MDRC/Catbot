class Motor():
    """
    Represents a motor that will control the hip, giving the leg abduction
    and adduction motion.
    """

    pin : int
    current_value : float = 0.0
    min_value : float       # signal to rotate at max speed in one direction 
    middle_value : float    # signal to stop rotation
    max_value : float       # signal to rotate at max speed in other direction

    def __init__(self,
                 pin : int, 
                 min_value : float,
                 middle_value : float,
                 max_value : float) -> None:
        """
        Initialize a new instance of a motor. There should be only one Motor object
        per real-world motor.

        :param pin: pin to send motor signals to
        :param min_value: signal to send to rotate motor fully in one direction
        :param middle_value: signal to send to stop motor rotation
        :param max_value: signal to send to rotate motor fully in other direction
        """
        self.pin = pin
        self.min_value = min_value
        self.middle_value = middle_value
        self.max_value = max_value
        ...

    def send_signal(value : int) -> None:
        """
        Send a signal directly to the motor.

        :param value: signal to send; cannot be above max_value or below min_value
        """
        ...

    def run(direction : int, time : int) -> None:
        """
        Rotate the motor in the given direction for the given amount of time.

        TODO: add params
        """
        ...

    def run(direction : int) -> None:
        """
        Rotate the motor in the given direction indefinitely.

        TODO: add params
        """
        ...

    def stop() -> None:
        """
        Stop all motor rotation.
        """
        ...