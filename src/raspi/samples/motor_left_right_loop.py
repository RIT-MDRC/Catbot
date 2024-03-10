import asyncio
from time import sleep

from component.motor import raw_motor_action
from state_management import configure_device

RIGHT_SPEED = -0.1  # unit: %
LEFT_SPEED = 0.1  # unit: %

configure_device("src/raspi/pinconfig.json")


while True:
    print("Moving left")
    asyncio.run(raw_motor_action.set_speed_direction("motor_1", value=LEFT_SPEED))
    sleep(3)
    print("Moving right")
    asyncio.run(raw_motor_action.set_speed_direction("motor_1", value=RIGHT_SPEED))
    sleep(3)
