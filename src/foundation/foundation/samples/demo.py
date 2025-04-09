import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from dataclasses import dataclass

from component.adc import adc_actions
from component.compressor import compressor_actions
from component.motor import motor_actions
from component.muscle import muscle_actions
from component.potentiometer import potentiometer_actions
from state_management import configure_device

adc_actions.USE = True

configure_device("samples/demo_config.json")


@dataclass
class Leg:
    motor: str
    muscle: str

    # Default speed and delays will be used for all of the legs unless overridden
    # when creating this class instance below
    leftSpeed: int = 10
    rightSpeed: int = -10
    stopSpeed: int = 0
    leftDelay: float = 1
    rightDelay: float = 1
    muscleDelay: float = 1
    cycleInterval: float = 1


@dataclass
class Compressor:
    compressor: str
    potentiometer: str

    # Pressure check parameters will be shared among all compressor objects unless
    # overridden for that specific compressor when creating this class instance
    minPressure: int = (
        100  # unit: PSI turns on the compressor when pressure is below this value
    )
    maxPressure: int = (
        120  # unit: PSI turns off the compressor when pressure is above this value
    )
    checkInterval: float = 1  # unit: seconds


LEGS = [
    Leg(
        motor="odrive_1",
        muscle="muscle_1",
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    Leg(
        motor="odrive_2",
        muscle="muscle_2",
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
]
COMPRESSOR = Compressor(
    compressor="main_compressor",
    potentiometer="pressure_sensor",
    # minPressure=100,
    # maxPressure=120,
    # checkInterval=1,
)


async def main(leg: Leg):
    # This is a simple demo that will move the leg back and forth and contract and expand the muscle in a cycle.
    # Each leg will move in a cycle independently.
    while True:
        motor_actions.set_target_velocity(
            leg.motor,
            leg.leftSpeed,
        )
        await asyncio.sleep(leg.leftDelay)
        motor_actions.set_target_velocity(leg.motor, leg.stopSpeed)
        muscle_actions.contract(leg.muscle)
        await asyncio.sleep(leg.muscleDelay)
        motor_actions.set_target_velocity(
            leg.motor,
            leg.rightSpeed,
        )
        await asyncio.sleep(leg.rightDelay)
        motor_actions.set_target_velocity(leg.motor, leg.stopSpeed)
        muscle_actions.relax(leg.muscle)
        await asyncio.sleep(leg.muscleDelay)
        await asyncio.sleep(leg.cycleInterval)


async def pressure_demo(compressor: Compressor):
    # This is a function that will turn on and off the compressor to maintain pressure in the pneumatics.
    # It will cycle between 100 and 120 PSI.
    def check_pressure():
        # Return True if pressure is too low, False if pressure is too high, None if pressure is within range

        pressure = potentiometer_actions.get_degree(compressor.potentiometer)

        print(pressure)

        return (
            True
            if pressure < compressor.minPressure
            else False if pressure > compressor.maxPressure else None
        )

    # For debouncing the compressor state
    compressor_state = False

    while True:
        check_res = check_pressure()
        if check_res and not compressor_state:
            compressor_actions.turn_compressor_on()
            compressor_state = True
        elif check_res is False and compressor_state:
            compressor_actions.turn_compressor_off()
            compressor_state = False
        await asyncio.sleep(compressor.checkInterval)


async def run_all():
    # Gather all tasks and run them concurrently
    await asyncio.gather(
        *[main(leg) for leg in LEGS],
        pressure_demo(COMPRESSOR)
    )

if __name__ == "__main__":
    asyncio.run(run_all())

# if __name__ == "__main__":
#     # Run the demo for each leg concurrently forever
#     asyncio.run(
#         asyncio.gather(
#             # *[asyncio.create_task(main(leg)) for leg in LEGS],
#             asyncio.create_task(pressure_demo(COMPRESSOR))
#         )
#     )
#     asyncio.get_event_loop().run_forever()
