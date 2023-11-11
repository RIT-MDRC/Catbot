from gpiozero import PWMOutputDevice

class Motor():
    """
    Represents a motor that will control the hip, giving the leg abduction
    and adduction motion.
    """

    direction : PWMOutputDevice
    pwm : PWMOutputDevice

    def __init__(self, direction_pin : int, pwm_pin : int) -> None:
        """
        Initialize a new instance of a motor. There should be only one Motor object
        per real-world motor.

        :param direction_pin: pin to send direction signal to
        :param pwm_pin: pin to send motor speed signal to;
        """
        self.direction = PWMOutputDevice(direction_pin)
        self.pwm = PWMOutputDevice(pwm_pin)

    def run(self, clockwise : bool, speed_percent : float) -> None:
        """
        Rotate the motor in the given direction for the given amount of time.

        :param clockwise: direction of rotation when viewing motor from front of output shaft
        :param speed_percent: [0, 100] percentage of maximum motor speed to operate at;
        generally should NOT be greater than 50
        """
        self.direction.value = 1 if clockwise else 0
        self.pwm.value = speed_percent / 100.0

    def stop(self) -> None:
        """
        Stop the rotation of the motor.
        """
        self.pwm.value = 0