import asyncio
from time import sleep

from component.motor import motor_actions, motor_enums
from state_management import configure_device

RIGHT_SPEED = -50  # unit: %
LEFT_SPEED = 70  # unit: %

configure_device("src/raspi/pinconfig.json")


async def main():
    motor_actions.set_target_velocity(
        "odrive_2",
    )
