from time import sleep

from component.latch import latch_actions
from component.motor import raw_motor_action
from state_management import configure_device

use = (raw_motor_action.ctx, latch_actions.ctx)

RIGHT_SPEED = -0.1  # unit: %
LEFT_SPEED = 0.1  # unit: %

configure_device("src/raspi/samples/pinconfig.json")


while True:
    print("Moving left")
    raw_motor_action.set_speed_direction("motor_1", value=LEFT_SPEED)
    sleep(3)
    print("Moving right")
    raw_motor_action.set_speed_direction("motor_1", value=RIGHT_SPEED)
    sleep(3)
