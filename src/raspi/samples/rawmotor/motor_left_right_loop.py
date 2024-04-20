import asyncio
from time import sleep

from component.motor import raw_motor_action
from state_management import configure_device

RIGHT_SPEED = -50  # unit: %
LEFT_SPEED = 70  # unit: %

configure_device("src/raspi/pinconfig.json")


while True:
    print("Moving left")
    asyncio.run(raw_motor_action.set_speed_percentage("motor_1", LEFT_SPEED))
    sleep(5)
    print("Moving right")
    asyncio.run(raw_motor_action.set_speed_percentage("motor_1", RIGHT_SPEED))
    sleep(5)
