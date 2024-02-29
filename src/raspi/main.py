from time import sleep

from component import MotorController, compressor_actions, muscle_actions
from component.muscle.pneumatics import pressure_actions
from state_management import (
    clear_intervals,
    configure_device,
    configure_logger,
    setup_cpu,
)
from view.pygame import *

SPEED = 0.1  # unit: %

global motor
"""Global variables for pygame"""


def setup():
    """Setup the pins and pygame"""
    configure_device("src/raspi/pinconfig.json")
    motor = MotorController(26, 0, 1, [5, 6, 12])
    logging.info("Initialized components from pinconfig")
    return motor


def hydrate_screen():
    """Post setup for the screen (after pygame.init() and global variable are set)"""
    logging.info("Hydrating Screen with initial values")
    render_pressure_status(False)
    render_up_status(False)
    render_left_status(False)
    render_right_status(False)
    render_temperature_status(0)
    update_screen()
    logging.info("Screen Hydrated")
    if pressure_actions.is_pressure_ok("left_pressure"):
        change_compressor(True)
    pressure_actions.on_pressure_active(
        "left_pressure",
        lambda: change_compressor(True),
    )
    pressure_actions.on_pressure_deactive(
        "left_pressure",
        lambda: change_compressor(False),
    )
    setup_cpu(render_temperature_status)  # Hook up CPU temp to the screen
    logging.info("Completed Screen Update Events")


def main():
    """Main program loop"""
    exit = False
    while not exit:
        for event in get_keys():
            if is_event_type(event, "down"):
                if is_key_pressed(event, ["w", "up"]):
                    if muscle_actions.contract("left_muscle"):
                        render_up_status(True)
                elif is_key_pressed(event, ["a", "left"]):
                    if turn_motor_left(SPEED):
                        render_left_status(True)
                elif is_key_pressed(event, ["d", "right"]):
                    if turn_motor_right(SPEED):
                        render_right_status(True)
                elif is_key_pressed(event, ["t"]):
                    step(motor)
                elif is_key_pressed(event, ["q"]):
                    exit = True
            elif is_event_type(event, "up"):
                if is_key_pressed(event, ["w", "up"]):
                    if muscle_actions.relax("left_muscle"):
                        render_up_status(False)
                elif is_key_pressed(event, ["a", "left"]):
                    if turn_motor_left(0):
                        render_left_status(False)
                elif is_key_pressed(event, ["d", "right"]):
                    if turn_motor_right(0):
                        render_right_status(False)
        update_screen()
        clock_tick(60)
    print("Exiting...")
    logging.info("Exiting...")
    quit_pygame()
    clear_intervals()


def change_compressor(status: bool):
    """Renders the compressor status

    Args:
        status(bool): the status to render
    """
    action = (
        compressor_actions.turn_compressor_on
        if status
        else compressor_actions.turn_compressor_off
    )
    action("main_compressor")
    render_pressure_status(status)


def turn_motor_left(speed):
    """Turns the motor left

    Args:
        speed(float): the speed to turn the motor at
    """
    return motor.set_speed_dir(speed, 1)


def turn_motor_right(speed):
    """Turns the motor right

    Args:
        speed(float): the speed to turn the motor at
    """
    return motor.set_speed_dir(speed, 0)


def step():
    muscle_actions.contract("left_muscle")
    sleep(1)
    turn_motor_right(SPEED)
    sleep(1)
    turn_motor_right(0)
    sleep(1)
    muscle_actions.relax("left_muscle")
    sleep(1)
    turn_motor_left(SPEED)
    sleep(1)
    turn_motor_left(0)
    sleep(1)


if __name__ == "__main__":
    configure_logger()
    logging.info("Initializing...")
    print("Initializing...")
    motor = setup()  # TODO: make motor not a global variable
    setup_pygame()  # global variables
    hydrate_screen()  # hydrate the screen
    print("Initialization complete!")
    main()
