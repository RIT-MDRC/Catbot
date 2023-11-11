from component_io.motor import Motor
import time

print("Meow! This is catbot cli v2")

test_motor = Motor(26, 21)

test_motor.run(clockwise=False, speed_percent=15)

input()
test_motor.stop()

time.sleep(100)