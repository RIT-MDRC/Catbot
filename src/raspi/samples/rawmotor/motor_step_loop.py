import asyncio
from time import sleep

from component.motor import raw_motor_action
from state_management import configure_device

RIGHT_STEP = 7
LEFT_STEP = 7

configure_device("src/raspi/pinconfig.json")


while True:
    print("Moving left")
    asyncio.run(raw_motor_action.step_n("motor_1", LEFT_STEP))
    sleep(5)
    print("Moving right")
    asyncio.run(raw_motor_action.step_n("motor_1", RIGHT_STEP))
    sleep(5)
