from gpiozero import PWMOutputDevice

from utils.util import create_output_device


class MotorController:
    motor = None
    PWM_Pin = None
    last_speed = 0
    last_direction = 0  # 0 for forward, 1 for backward

    def __init__(self, PWM_Pin, address):
        self.PWM_Pin = (
            PWM_Pin  # Pin that recieves the PWM speed value. 26 for MakerFaire
        )
        self.address = address  # value 0-7 representing address for directional control
        self.motor = PWMOutputDevice(PWM_Pin)
        ## These are the same for all motors
        self.direction_pin = create_output_device(1)
        self.address_p0 = create_output_device(5)
        self.address_p1 = create_output_device(6)
        self.address_p2 = create_output_device(12)

    motor = None  # 26 yellow, 16 red

    ### THIS IS PRIVATE, DON'T F***ING USE IT! ~CR ###
    # Parses a decimal number into an array of bits
    def bitfield(self, n):
        return [int(digit) for digit in bin(n)[2:]]  # [2:] to chop off the "0b" part

    # Uses Addressable Latch Direction Control to set the ESC at the address for this motor
    # this is a helper method and should not be used outside this file unless absolutely
    # needed.
    def set_direction(self, direction):
        bits = self.bitfield(self.address)
        bits.reverse()

        while len(bits) < 3:
            bits.append(0)

        self.direction_pin.value = direction
        self.address_p0.value = bits[0]
        self.address_p1.value = bits[1]
        self.address_p2.value = bits[2]

    # helper method for controling speed, can be used but should be avoided
    def set_PWM(self, speed):
        self.motor.value = speed

    ### USE THIS ONE ###
    # Method for setting this ESC to a given speed and direction
    def set_Motor(self, speed, direction):
        print(f"motor called {speed} {direction}")
        if speed != 0 and self.last_speed != 0 and self.last_direction != direction:
            print("ERROR: Motor direction and speed do not match")
            return False
        self.set_PWM(speed)
        self.set_direction(direction)
        self.last_direction = direction
        self.last_speed = speed
        return True
