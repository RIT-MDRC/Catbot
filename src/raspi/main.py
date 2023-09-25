# Code for testing the Raspberry Pi's PWM signal capabilities.
# Code from https://randomnerdtutorials.com/raspberry-pi-pwm-python/#:~:text=Python%20Script%20%E2%80%93%20PWM%20on%20Raspberry%20Pi%20GPIOs

from gpiozero import PWMLED
from time import sleep

PINLIST = [14, 15, 23, 24, 4, 17, 27, 22]
pwms = []
for pin in PINLIST:
    pwms.append(PWMLED(pin))

for pwm in pwms:
    pwm.value = 0
sleep(1)
for pwm in pwms:
    pwm.value = 1
sleep(1)
for pwm in pwms:
    pwm.value = 0
sleep(1)

try:
    # fade in and out forever
    while True:
        # fade in
        print("Fade in")
        for duty_cycle in range(0, 100, 1):
            for pwm in pwms:
                pwm.value = duty_cycle / 100.0
            sleep(0.05)

        # fade out
        print("Fade out")
        for duty_cycle in range(100, 0, -1):
            for pwm in pwms:
                pwm.value = duty_cycle / 100.0
            sleep(0.05)

except KeyboardInterrupt:
    print("Stop the program and turning off the LED")
    for pwm in pwms:
        pwm.value = 0
    pass
