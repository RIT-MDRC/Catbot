from control.motor import MotorController

ctrl = MotorController(pot_channel=0, motor_dir_pin=26, motor_pwm_pin=21, limit_interrupt_pin=20)
ctrl.rotate_to(200, 5)