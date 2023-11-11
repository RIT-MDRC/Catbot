from component_io.motor.motor import Motor
import time

print("Meow! This is catbot cli v2")

test_motor = Motor(26, 21)

test_motor.run(clockwise=False, speed_percent=15)
time.sleep(10)