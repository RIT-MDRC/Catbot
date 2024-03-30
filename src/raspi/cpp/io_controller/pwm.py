from gpiozero import PWMOutputDevice
from time import sleep

possible_motor_pins = [26, 16, 19, 13, 4, 18, 17, 27]
motors = [PWMOutputDevice(pin) for pin in possible_motor_pins]

for motor in motors:
    motor.value = 0.25
    print(motor.value)

sleep(30)