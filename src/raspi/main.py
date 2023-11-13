from control.motor import MotorController
from component_io.potentiometer import Potentiometer
from component_io.motor import Motor
import time

print("Meow! This is catbot cli v2")

ctrl = MotorController(pot_channel=0, motor_dir_pin=26, motor_pwm_pin=21)
ctrl.rotate_degrees(50, 5)