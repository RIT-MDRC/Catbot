# Sample motor rotation via PWM.
# 1. Rotate 5 seconds in each direction
# 2. Ramp up/down speed

# ESC pin       RPi GPIO
# DIR           23
# PWM           24

from gpiozero import PWMOutputDevice
from gpiozero import DigitalOutputDevice
from time import sleep

direction = PWMOutputDevice(11)
motor = PWMOutputDevice(26) #26 yellow, 16 red
gee = DigitalOutputDevice(0)

#Global ESC Enable Pulse
gee.value = 1

sleep(1)

gee.value = 0


# spin in one direction
direction.value = 1
motor.value = 0.1
print(f"spinning at {motor.value * 100}% duty cycle, direction {direction.value}")
sleep(5)

# spin in the other direction
direction.value = 0
motor.value = 0.2
print(f"spinning at {motor.value * 100}% duty cycle, direction {direction.value}")
sleep(5)

# stop for a bit
print(f"stop")
motor.value = 0
sleep(1)

i = 0
print(f"ramping up speed")
while i < 1:
    motor.value = i
    i += 0.05
    sleep(0.25)

i = 1
print(f"ramping down speed")
while i > 0:
    motor.value = i
    i -= 0.05
    sleep(0.25)


# motor.value = 0
print("end")
