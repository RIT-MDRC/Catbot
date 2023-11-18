from gpiozero import PWMOutputDevice
from gpiozero import DigitalOutputDevice


class Motor:
    def __init__(self,PWM_Pin,address):
        self.PWM_Pin # Pin that recieves the PWM speed value. 26 for MakerFaire
        self.address # value 0-7 representing address for directional control

## These are the same for all motors
direction_pin = DigitalOutputDevice(1)
address_p0 = DigitalOutputDevice(5)
address_p1 = DigitalOutputDevice(6)
address_p2 = DigitalOutputDevice(12)

motor = PWMOutputDevice(PWM_Pin) #26 yellow, 16 red


### THIS IS PRIVATE, DON'T F***ING USE IT! ~CR ### 
# Parses a decimal number into an array of bits
def bitfield(n):
    return [int(digit) for digit in bin(n)[2:]] # [2:] to chop off the "0b" part 

# Uses Addressable Latch Direction Control to set the ESC at the address for this motor
# this is a helper method and should not be used outside this file unless absolutely
# needed.
def set_direction(direction):
    bits = bitfield(self.address)
    bits.reverse()

    while(len(bits)<3):
        bits.append(0)


    direction_pin.value = direction
    address_p0.value = bits[0]
    address_p1.value = bits[1]
    address_p2.value = bits[2]

# helper method for controling speed, can be used but should be avoided
def set_PWM(speed):
    motor.value = speed


### USE THIS ONE ###
# Method for setting this ESC to a given speed and direction
def set_Motor(speed,direction):
    set_PWM(speed)
    set_direction(direction)

