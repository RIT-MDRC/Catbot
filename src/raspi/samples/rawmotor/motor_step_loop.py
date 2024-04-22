import asyncio
from time import sleep

from component.motor import raw_motor_action, step_pin_action
from state_management import configure_device
from component.latch import latch_actions

latch_actions.USE = True

LEFT_STEP = 30
RIGHT_STEP = -30

configure_device("src/raspi/pinconfig.json")


while True:
    print("Moving left")
    asyncio.run(raw_motor_action.step_n("motor_1", LEFT_STEP))
    sleep(1)
    print("Moving right")
    asyncio.run(raw_motor_action.step_n("motor_1", RIGHT_STEP))
    sleep(1)
