from gpiozero import PWMOutputDevice
import RPi.GPIO as GPIO
from time import sleep

PIN_PWM = 20

motor = PWMOutputDevice(PIN_PWM)
motor.value = 0.25

sleep(100)