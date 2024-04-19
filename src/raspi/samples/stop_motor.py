import asyncio
from time import sleep

from component.motor import raw_motor_action
from state_management import configure_device

RIGHT_SPEED = -50  # unit: %
LEFT_SPEED = 70  # unit: %

configure_device("src/raspi/pinconfig.json")

asyncio.run(raw_motor_action.stop("motor_1"))
while True:
    sleep(5)
