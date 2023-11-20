from utils.deviceMock import FakeOutputDevice, FakePWMOutputDevice
from utils.util import create_output_device, create_pwm_device
from gpiozero import PWMOutputDevice, OutputDevice


class MotorController:
    motor: FakePWMOutputDevice | PWMOutputDevice
    pwm_pin: int
    current_speed = 0
    current_direction = 0  # 0 for forward, 1 for backward
    address_output_devices: FakeOutputDevice | OutputDevice = []

    def __init__(
        self,
        pwm_pin: int,
        direction_address: int,
        direction_pin: int,
        address_pins: [int],
    ):
        self.pwm_pin = pwm_pin
        self.direction_address = (
            direction_address  # value 0-7 representing address for directional control
        )
        self.motor = create_pwm_device(pwm_pin)
        ## These are the same for all motors
        self.direction_pin = create_output_device(direction_pin)
        self.address_output_devices = [
            create_output_device(pin) for pin in address_pins
        ]

    def set_direction(self, direction) -> None:
        """
        Uses Addressable Latch Direction Control to set the ESC at the address for this motor
        this is a helper method and should not be used outside this file unless absolutely
        needed.
        """
        bits = bitfield(self.direction_address, len(self.address_output_devices))[::-1]
        self.direction_pin.value = direction
        for i, od in enumerate(self.address_output_devices):
            od.value = bits[i]

    def set_speed(self, speed) -> None:
        "helper method for controling speed, can be used but should be avoided"
        self.motor.value = speed

    def set_speed_dir(self, new_speed, new_direction) -> bool:
        "Method for setting this ESC to a given speed and direction"
        print(
            f"motor called {new_direction} {self.current_direction} {self.current_speed}"
        )
        if self.current_speed != 0 and self.current_direction != new_direction:
            print("ERROR: Motor direction and speed do not match")
            return False
        self.set_speed(new_speed)
        self.set_direction(new_direction)
        self.current_direction = new_direction
        self.current_speed = new_speed
        return True


def bitfield(n, length=3) -> str:
    """
    Parses a decimal number into a binary string
    Omits "0b" from the beginning of the string
    Adds leading zeros to make the array always 'length' bits long (default 3)
    """
    return format(n, f"0{length}b")
