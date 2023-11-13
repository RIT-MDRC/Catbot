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

    def rotate_to(self, target_rotation : float, percent_speed : float) -> None:
        """
        Rotate the gearbox until it reaches a given rotation.

        :param target_rotation: the target rotation of the motor (degrees)
        :param percent_speed: percentage of max speed to run motor at, range [0, 100];
        generally should NOT be greater than 50
        """
        clockwise = False

        # Even though turning the potentiometer clockwise increases its output voltage, the
        # motor turns in the opposite direction as the potentiometer since that's how gears work.
        if target_rotation < self.potentiometer.get_rotation():
            clockwise = True

        self.motor.run(clockwise, percent_speed)
        
        # Run the motor until we hit our target rotation
        if clockwise:
            while self.potentiometer.get_rotation() > target_rotation:
                print(self.potentiometer.get_rotation())
        else:
            while self.potentiometer.get_rotation() < target_rotation:
                print(self.potentiometer.get_rotation())

        print(f"Reached {str(target_rotation)} degrees")
        self.stop()

    def rotate_degrees(self, rotation_amount : float, percent_speed : float) -> None:
        """
        Rotate the gearbox some number of degrees from its current rotation.

        :param rotation_amount: number of degrees to rotate, where a negative value is clockwise
        :param percent_speed: percentage of max speed to run motor at, range [0, 100];
        generally should NOT be greater than 50
        """
        end_rotation = self.potentiometer.get_rotation() + rotation_amount
        self.rotate_to(end_rotation, percent_speed)

    def stop(self) -> None:
        """
        Stop rotation of the motor.
        """
        self.motor.stop()