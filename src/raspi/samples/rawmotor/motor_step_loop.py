import asyncio
from time import sleep

from component.motor import raw_motor_action, step_pin_action
from state_management import configure_device
from component.latch import latch_actions

latch_actions.USE = True

latches = (
    "latch_1",
    "latch_2",
    "latch_3",
    "latch_4",
    "latch_5",
    "latch_6",
    "latch_7",
    "latch_8",
)

RIGHT_STEP = 7
LEFT_STEP = 7

configure_device("src/raspi/pinconfig.json")


while True:
    print("Moving left")
    # raw_motor_action.switch_dir("motor_1", True)
    for n in latches:
        print(f"setting {n}")
        step_pin_action.set_direction_high(f"latch_1.{n}")
        sleep(0.5)
    asyncio.run(raw_motor_action.step_n("motor_1", LEFT_STEP))
    sleep(1)
    print("Moving right")
    # raw_motor_action.switch_dir("motor_1", False)
    for n in latches:
        print(f"setting {n}")
        step_pin_action.set_direction_low(f"latch_1.{n}")
        sleep(0.5)
    asyncio.run(raw_motor_action.step_n("motor_1", RIGHT_STEP))
    sleep(1)
