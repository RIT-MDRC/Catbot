import logging
from time import sleep

from component.compressor import compressor_actions
from component.motor import raw_motor_action
from component.muscle import muscle_actions
from component.muscle.pneumatics import pressure_actions
from state_management import clear_intervals, configure_device, setup_cpu
from view.pygame import *

LEFT_SPEED = 0.1  # unit: %
RIGHT_SPEED = -0.1  # unit: %


def setup():
    """Setup the pins and pygame"""
    configure_device("src/raspi/pinconfig.json")
    logging.info("Initialized components from pinconfig")


def hydrate_screen():
    """Post setup for the screen (after pygame.init() and global variable are set)"""
    logging.info("Hydrating Screen with initial values")
    logging.info("Hydrating Screen with initial values")
    render_pressure_status(False)
    render_up_status(False)
    render_left_status(False)
    render_right_status(False)
    render_temperature_status(0)
    update_screen()
    logging.info("Screen Hydrated")
    if pressure_actions.is_pressure_ok("left_pressure"):
    update_screen()
    logging.info("Screen Hydrated")
    if pressure_actions.is_pressure_ok("left_pressure"):
        change_compressor(True)
    pressure_actions.on_pressure_active(
    pressure_actions.on_pressure_active(
        "left_pressure",
        lambda: change_compressor(True),
    )
    pressure_actions.on_pressure_deactive(
    pressure_actions.on_pressure_deactive(
        "left_pressure",
        lambda: change_compressor(False),
    )
    setup_cpu(render_temperature_status)  # Hook up CPU temp to the screen
    logging.info("Completed Screen Update Events")


def main():
    """Main program loop"""
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
        for event in get_keys():
            if is_event_type(event, "down"):
                if is_key_pressed(event, ["w", "up"]):
                    if muscle_actions.contract("left_muscle"):
                        render_up_status(True)
                elif is_key_pressed(event, ["a", "left"]):
                    print("left call")
                    if raw_motor_action.set_speed_direction(
                        "motor_1", value=LEFT_SPEED
                    ):
                        render_left_status(True)
                elif is_key_pressed(event, ["d", "right"]):
                    print("right call")
                    if raw_motor_action.set_speed_direction(
                        "motor_1", value=RIGHT_SPEED
                    ):
                        render_right_status(True)
                elif is_key_pressed(event, ["t"]):
                    step()
                elif is_key_pressed(event, ["q"]):
                    exit = True
            elif is_event_type(event, "up"):
                if is_key_pressed(event, ["w", "up"]):
                    if muscle_actions.relax("left_muscle"):
                        render_up_status(False)
                elif is_key_pressed(event, ["a", "left"]):
                    if raw_motor_action.stop("motor_1"):
                        render_left_status(False)
                elif is_key_pressed(event, ["d", "right"]):
                    if raw_motor_action.stop("motor_1"):
                        render_right_status(False)
        update_screen()
        clock_tick(60)
    print("Exiting...")
    logging.info("Exiting...")
    quit_pygame()
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
    action = (
        compressor_actions.turn_compressor_on
        if status
        else compressor_actions.turn_compressor_off
    )
    action("main_compressor")
    render_pressure_status(status)


def step():
    muscle_actions.contract("left_muscle")
    muscle_actions.contract("left_muscle")
    sleep(1)
    raw_motor_action.set_speed_direction("motor_1", LEFT_SPEED)
    sleep(1)
    raw_motor_action.stop("motor_1")
    sleep(1)
    muscle_actions.relax("left_muscle")
    muscle_actions.relax("left_muscle")
    sleep(1)
    raw_motor_action.set_speed_direction("motor_1", -LEFT_SPEED)
    sleep(1)
    raw_motor_action.stop("motor_1")
    sleep(1)


if __name__ == "__main__":
    print("Initializing...")
    setup()  # TODO: make motor not a global variable
    setup_pygame()  # global variables
    hydrate_screen()  # hydrate the screen
    print("Initialization complete!")
    main()
