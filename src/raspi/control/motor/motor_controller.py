from component_io.motor import Motor
from component_io.potentiometer import Potentiometer

class MotorController():
    """
    Represents an entire gearbox assembly (half of one hip).
    """

    motor : Motor
    potentiometer : Potentiometer

    def __init__(self,
                 pot_channel : int,
                 motor_dir_pin : int,
                 motor_pwm_pin : int) -> None:
        """
        Initialize a new instance of a motor controller. There should only be one
        instance of MotorController per real-world motor.

        :param pot_channel: ADC channel this motor's potentiometer is connected to
        :param motor_dir_pin: pin to send motor direction signal to
        :param motor_pwm_pin: pin to send motor speed signal to
        """
        self.motor = Motor(motor_dir_pin, motor_pwm_pin)
        self.potentiometer = Potentiometer(pot_channel)

    def run(self, percent_speed : float, rotation : float) -> None:
        """
        Rotate the motor until it reaches a given rotation.

        :param percent_speed: percentage of max speed to run motor at, range [0, 100];
        generally should NOT be greater than 50
        :param rotaiton: the target rotation of the motor (degrees)
        """
        clockwise = False

        if rotation < self.potentiometer.get_rotation():
            clockwise = True

        self.motor.run(clockwise, percent_speed)
        
        if clockwise:
            while self.potentiometer.get_rotation() > rotation:
                print(self.potentiometer.get_rotation())
        else:
            while self.potentiometer.get_rotation() < rotation:
                print(self.potentiometer.get_rotation())
        self.stop()

    def stop(self) -> None:
        """
        Stop rotation of the motor.
        """
        self.motor.stop()