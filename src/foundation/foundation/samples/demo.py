import os
import sys
import numpy as np

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
    motor: str # flex and extension motor
    muscle: str

    # Default speed and delays will be used for all of the legs unless overridden
    # when creating this class instance below
    leftSpeed: int = 1
    rightSpeed: int = -1
    stopSpeed: int = 0

    # no such thing as left and right in one leg
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
        75  # unit: PSI turns on the compressor when pressure is below this value
    )
    maxPressure: int = (
        80 # unit: PSI turns off the compressor when pressure is above this value
    )
    checkInterval: float = 0.5  # unit: seconds


LEGS = [
    # front left
    Leg(
        motor="odrive_1",
        # abd_ad="odrive_2",
        muscle="muscle_1",
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    # back left
    Leg(
        motor="odrive_3",
        # abd_ad="odrive_4",
        muscle="muscle_2",
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    # back right
    Leg(
        motor="odrive_5",
        # abd_ad="odrive_6",
        muscle="muscle_3",
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    # front right
    Leg(
        motor="odrive_7",
        # abd_ad="odrive_8",
        muscle="muscle_4",
        # Uncomment to override default speed and delays
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

SLEEP_TIME = 1
ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND = .0027760417
DEFAULT_TORQUE = .001

def convert_degrees_to_positions(n: float):
    return n * (5.33/30) # 5.33 positions per 30 degrees

async def startup(leg: Leg):
    pos = motor_actions.get_current_position(leg.motor)

async def main(leg: Leg):
    # This is a simple demo that will move the leg back and forth and contract and expand the muscle in a cycle.
    # Each leg will move in a cycle independently.

    startup(leg)
    while motor_actions.get_state(leg.motor) != motor_actions.MotorState.IDLE:
        print(f"Calibrating {leg.motor}...")
    await asyncio.sleep(3)
    if motor_actions.set_controller_mode(leg.motor, motor_actions.ControlMode.POSITION_CONTROL):
        print("main")

    print("main2")

    motor_actions.set_position_control_velocity(leg.motor, ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND)

    degrees = convert_degrees_to_positions(30)

    while True:
        # motor_actions.set_controller_mode(leg.motor, motor_actions.ControlMode.POSITION_CONTROL)
        motor_actions.set_target_position(
            leg.motor,
            degrees,
            ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND
        )
        await asyncio.sleep(leg.leftDelay)
        motor_actions.set_target_position(leg.motor, 0, ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND)
        # muscle_actions.contract(leg.muscle)
        await asyncio.sleep(leg.muscleDelay)
        motor_actions.set_target_position(
            leg.motor,
            degrees * -1,
            ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND
        )
        await asyncio.sleep(leg.rightDelay)
        motor_actions.set_target_position(leg.motor, 0,ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND )
        # muscle_actions.relax(leg.muscle)
        await asyncio.sleep(leg.muscleDelay)
        await asyncio.sleep(leg.cycleInterval)


TWO_PI = 2 * np.pi
THREE_PI_HALVES = 3 * np.pi_half / 2
PI_HALF = np.pi / 2

async def gait_cycle(leg: Leg, degrees: float, time: int, steps: int, phase: float):
        """
        degrees: length of gait in degrees
                    (step size)
        time: total time for whole cycle
        steps: number of steps to break the walking portion into
        phase: phase in radians to start at, each leg
                    starting leg phase should be 0
        """
        gait = convert_degrees_to_positions(degrees) / 2.0
        time_between = time / steps
        steps_per_second = steps / time
        angular_frequency = TWO_PI / steps_per_second 
        current_phase = phase
        current_phase = (current_phase + angular_frequency)
        pos = gait * np.cos(current_phase)
        motor_actions.set_target_position(
            leg.motor,
            -1*(pos),
        )
        if(current_phase == 0):
            motor_actions.release()
        if (current_phase == time):
            motor_actions.contract()
        current_phase = current_phase % time
        await asyncio.sleep(time_between)

async def pressure_demo(compressor: Compressor):
    # This is a function that will turn on and off the compressor to maintain pressure in the pneumatics.
    # It will cycle between 100 and 120 PSI.
    def check_pressure():
        # Return True if pressure is too low, False if pressure is too high, None if pressure is within range

        pressure = potentiometer_actions.get_psi(potentiometer_actions.get_data(compressor.potentiometer))

        print(str(pressure) + " degree")
        print(str(potentiometer_actions.get_data(compressor.potentiometer)) + " raw data")

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
            compressor_actions.turn_compressor_on(compressor.compressor)
            compressor_state = True
        elif check_res is False and compressor_state:
            compressor_actions.turn_compressor_off(compressor.compressor)
            compressor_state = False
        await asyncio.sleep(compressor.checkInterval)


async def run_all():
    # Gather all tasks and run them concurrently
    await asyncio.gather(
        # *[main(leg) for leg in LEGS]
        # main(LEGS[0]),
        main(LEGS[1]),
        # main(LEGS[2]),
        # main(LEGS[3]),
        # pressure_demo(COMPRESSOR)
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
