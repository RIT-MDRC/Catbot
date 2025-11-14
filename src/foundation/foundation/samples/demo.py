import os
import sys
import time

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

DEGREES = 7
TWO_PI = 2 * np.pi
STEPS = 60  # total per cycle
TIME = 5  # in seconds
TIME_PER_STEP = TIME / STEPS
STEPS_PER_SECOND = STEPS / TIME
ANGULAR_FREQUENCY = TWO_PI / STEPS


@dataclass
class Leg:
    motor: str  # flex and extension motor
    abd_ad: str  # abductor and aductor (i can't spell) motor
    muscle: str
    appendage: str  # which leg this represents as in FRONT_RIGHT, BACK_RIGHT, FRONT_LEFT, BACK_LEFT
    side: int  # left is -1 right is pos 1, do no do different values than this, used for compressor

    # phase, used for gait cycle, is either 0 pi/2 pi or 3pi/2
    # because the gait cycle is based on a cosine loop
    phase: float = 0

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
        80  # unit: PSI turns off the compressor when pressure is above this value
    )
    checkInterval: float = 0.5  # unit: seconds


LEGS = [
    # front left
    Leg(
        motor="odrive_1",
        abd_ad="odrive_2",
        muscle="muscle_1",
        appendage="FRONT_LEFT",
        phase=0,
        side=-1,
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    # back left
    Leg(
        motor="odrive_3",
        abd_ad="odrive_4",
        muscle="muscle_2",
        appendage="BACK_LEFT",
        phase=np.pi,
        side=-1,
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    # back right
    Leg(
        motor="odrive_5",
        abd_ad="odrive_6",
        muscle="muscle_3",
        appendage="BACK_RIGHT",
        phase=np.pi,
        side=1,
        # Uncomment to override default speed and delays
        # leftSpeed=LEFT_SPEED,
        # rightSpeed=RIGHT_SPEED,
        # leftDelay=1,
        # rightDelay=1,
    ),
    # front right
    Leg(
        motor="odrive_7",
        abd_ad="odrive_8",
        muscle="muscle_4",
        appendage="FRONT_RIGHT",
        phase=0,
        side=1,
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
ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND = 0.0027760417
DEFAULT_TORQUE = 0.001


def convert_degrees_to_positions(n: float):
    return n * (5.33 / 30)  # 5.33 positions per 30 degrees


def calibrate():
    print("back left calibration")
    motor_actions.set_axis_state(
        LEGS[1].motor, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(1)
    motor_actions.set_axis_state(
        LEGS[1].abd_ad, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(20)
    print("back left homing")
    motor_actions.set_axis_state(LEGS[1].motor, motor_actions.MotorState.HOMING)
    time.sleep(1)
    motor_actions.set_axis_state(LEGS[1].abd_ad, motor_actions.MotorState.HOMING)
    time.sleep(10)
    print("back right calibration")
    motor_actions.set_axis_state(
        LEGS[2].motor, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(1)
    motor_actions.set_axis_state(
        LEGS[2].abd_ad, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(20)
    print("back right homing")
    motor_actions.set_axis_state(LEGS[2].motor, motor_actions.MotorState.HOMING)
    time.sleep(1)
    motor_actions.set_axis_state(LEGS[2].abd_ad, motor_actions.MotorState.HOMING)
    time.sleep(10)
    print("front right calibration")
    motor_actions.set_axis_state(
        LEGS[3].motor, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(1)
    motor_actions.set_axis_state(
        LEGS[3].abd_ad, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    print("front right homing")
    motor_actions.set_axis_state(LEGS[3].motor, motor_actions.MotorState.HOMING)
    time.sleep(1)
    motor_actions.set_axis_state(LEGS[3].abd_ad, motor_actions.MotorState.HOMING)
    time.sleep(10)
    print("front left calibration")
    motor_actions.set_axis_state(
        LEGS[0].motor, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(1)
    motor_actions.set_axis_state(
        LEGS[0].abd_ad, motor_actions.MotorState.FULL_CALIBRATION_SEQUENCE
    )
    time.sleep(20)
    print("front left homing")
    motor_actions.set_axis_state(LEGS[0].motor, motor_actions.MotorState.HOMING)
    time.sleep(1)
    motor_actions.set_axis_state(LEGS[0].abd_ad, motor_actions.MotorState.HOMING)
    time.sleep(10)

    for leg in LEGS:
        if motor_actions.set_axis_state(
            leg.motor, motor_actions.MotorState.CLOSED_LOOP_CONTROL
        ):
            print("leg flex in closed loop")
        if motor_actions.set_axis_state(
            leg.abd_ad, motor_actions.MotorState.CLOSED_LOOP_CONTROL
        ):
            print("leg abd in closed loop")


def startup(degrees: float, compressor: Compressor):

    # this section moves the legs to their correct starting position given the amble gait cycle

    for leg in LEGS:
        if motor_actions.set_controller_mode(
            leg.motor, motor_actions.ControlMode.POSITION_CONTROL
        ):
            print("leg flex in position_control")
    time.sleep(1)

    for leg in LEGS:
        gait_cycle(leg, degrees, 0, compressor)

    print("startup complete")
    time.sleep(5)


async def main(leg: Leg, degrees: float, compressor: Compressor):

    i = 1
    while True:
        gait_cycle(leg, degrees, i, compressor)
        await asyncio.sleep(TIME_PER_STEP)
        # motor_actions.set_target_position(
        #     leg.motor,
        #     degrees,
        #     ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND
        # )
        # await asyncio.sleep(leg.leftDelay)
        # motor_actions.set_target_position(leg.motor, 0, ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND)
        # # muscle_actions.contract(leg.muscle)
        # await asyncio.sleep(leg.muscleDelay)
        # motor_actions.set_target_position(
        #     leg.motor,
        #     degrees * -1,
        #     ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND
        # )
        # await asyncio.sleep(leg.rightDelay)
        # motor_actions.set_target_position(leg.motor, 0,ONE_DEGREE_PER_SECOND_IN_REV_PER_SECOND )
        # # muscle_actions.relax(leg.muscle)
        # await asyncio.sleep(leg.muscleDelay)
        # await asyncio.sleep(leg.cycleInterval)
        i += 1


def gait_cycle(leg: Leg, degrees: float, current_step: int, compressor: Compressor):
    """
    does one "cycle" not as in a full cycle, as in one part ie one "2pi / steps/time" of a cycle
    the gait is broken into chunks, size of which is defined by steps/time,
    so calling this method once would do one increment of that total cycle


    degrees: length of gait in degrees
                (step size)
    time: total time for whole cycle (is constant)
    steps: number of steps to break the walking portion into (is constant)
    phase: phase in radians to start at, each leg
                starting leg phase should be 0 (it is assumed 0 is leg down and perpendicular to the ground)
    """

    gait = convert_degrees_to_positions(degrees) / 2.0
    leg_pos_in_radians = ANGULAR_FREQUENCY * current_step + leg.phase
    leg_degree = gait * np.cos(leg_pos_in_radians)
    motor_actions.set_target_position(
        leg.motor,
        -1 * (leg_degree),  # might depend on which leg
    )
    if leg.side * np.sin(leg_pos_in_radians) < 0:
        muscle_actions.relax(leg.muscle)
    if leg.side * np.sin(leg_pos_in_radians) > 0:
        if (
            potentiometer_actions.get_psi(
                potentiometer_actions.get_data(compressor.potentiometer)
            )
            >= 75
        ):
            muscle_actions.contract(leg.muscle)


async def pressure_demo(compressor: Compressor):
    # This is a function that will turn on and off the compressor to maintain pressure in the pneumatics.
    # It will cycle between 75 and 80 PSI.
    def check_pressure():
        # Return True if pressure is too low, False if pressure is too high, None if pressure is within range

        pressure = potentiometer_actions.get_psi(
            potentiometer_actions.get_data(compressor.potentiometer)
        )

        print(str(pressure) + " PSI")
        # print(str(potentiometer_actions.get_data(compressor.potentiometer)) + " raw data")

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


async def run_all(degrees: float, compressor: Compressor):
    # Gather all tasks and run them concurrently
    await asyncio.gather(
        main(LEGS[0], degrees, compressor),
        main(LEGS[1], degrees, compressor),
        main(LEGS[2], degrees, compressor),
        main(LEGS[3], degrees, compressor),
        pressure_demo(compressor),  # comment out to stop pressure
    )


if __name__ == "__main__":
    calibrate()
    startup(DEGREES, COMPRESSOR)
    print("beginning main loop")
    asyncio.run(run_all(DEGREES, COMPRESSOR))
