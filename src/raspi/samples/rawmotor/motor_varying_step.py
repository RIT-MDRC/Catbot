import asyncio
from time import sleep

from component.motor import raw_motor_action
from state_management import configure_device

RANGE = 30

configure_device("src/raspi/pinconfig.json")

while True:
    for n in range(RANGE):
        asyncio.run(raw_motor_action.step_n("motor_1", n))
        sleep(1)
