# Code for testing the Raspberry Pi's PWM signal capabilities.
# Code from https://randomnerdtutorials.com/raspberry-pi-pwm-python/#:~:text=Python%20Script%20%E2%80%93%20PWM%20on%20Raspberry%20Pi%20GPIOs

from gpiozero import PWMLED
from time import sleep

led0 = PWMLED(14)
led1 = PWMLED(15)
led2 = PWMLED(23)
led3 = PWMLED(24)

led0.value = 1  # LED fully on
led1.value = 1  # LED fully on
led2.value = 1  # LED fully on
led3.value = 1  # LED fully on
sleep(1)
led0.value = 0.5  # LED half-brightness
led1.value = 0.5  # LED half-brightness
led2.value = 0.5  # LED half-brightness
led3.value = 0.5  # LED half-brightness
sleep(1)
led0.value = 0  # LED fully off
led1.value = 0  # LED fully off
led2.value = 0  # LED fully off
led3.value = 0  # LED fully off
sleep(1)

try:
    # fade in and out forever
    while True:
        # fade in
        for duty_cycle in range(0, 100, 1):
            led0.value = duty_cycle / 100.0
            led1.value = duty_cycle / 100.0
            led2.value = duty_cycle / 100.0
            led3.value = duty_cycle / 100.0
            sleep(0.05)

        # fade out
        for duty_cycle in range(100, 0, -1):
            led0.value = duty_cycle / 100.0
            led1.value = duty_cycle / 100.0
            led2.value = duty_cycle / 100.0
            led3.value = duty_cycle / 100.0
            sleep(0.05)

except KeyboardInterrupt:
    print("Stop the program and turning off the LED")
    led0.value = 0
    led1.value = 0
    led2.value = 0
    led3.value = 0
    pass
