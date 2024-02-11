from time import sleep

import pygame
from control.motor.motor_controller import MotorController
from control.muscle.muscle_controller import contract, relax
from io_controller import compressor_actions as comp
from io_controller import pressure_actions as press
from utils.cpu import setup_cpu
from utils.interval import clear_intervals
from utils.util import *
from view.pygame import *

SPEED = 0.1

global motor
"""Global variables for pygame"""


def setup():
    """Setup the pins and pygame"""
    data = get_pinconfig()
    set_pin(data)
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
    pygame.display.update()
    logging.info("Screen Hydrated")
    if press.is_pressure_ok("left_pressure"):
        change_compressor(True)
    press.on_pressure_active(
        "left_pressure",
        lambda: change_compressor(True),
    )
    press.on_pressure_deactive(
        "left_pressure",
        lambda: change_compressor(False),
    )
    setup_cpu(render_temperature_status)  # Hook up CPU temp to the screen
    logging.info("Completed Screen Update Events")


def main():
    """Main program loop"""
    exit = False
    while not exit:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    exit = True
                elif event.key == pygame.K_w or event.key == pygame.K_UP:
                    res = contract("left_muscle")
                    if res:
                        render_up_status(True)
                elif event.key == pygame.K_a or event.key == pygame.K_LEFT:
                    res = turn_motor_left(SPEED)
                    if res:
                        render_left_status(True)
                elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                    res = turn_motor_right(SPEED)
                    if res:
                        render_right_status(True)
                elif event.key == pygame.K_t:
                    step(motor)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_a or event.key == pygame.K_LEFT:
                    res = turn_motor_left(0)
                    if res:
                        render_left_status(False)
                elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                    res = turn_motor_right(0)
                    if res:
                        render_right_status(False)
                elif event.key == pygame.K_w or event.key == pygame.K_UP:
                    res = relax("left_muscle")
                    if res:
                        render_up_status(False)
            elif event.type == pygame.QUIT:
                exit = True
        pygame.display.update()
        clock_tick(60)
    print("Exiting...")
    logging.info("Exiting...")
    pygame.quit()
    clear_intervals()


def change_compressor(status: bool):
    """Renders the compressor status

    Args:
        status(bool): the status to render
    """
    action = comp.turn_compressor_on if status else comp.turn_compressor_off
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
    contract("left_muscle")
    sleep(1)
    turn_motor_right(SPEED)
    sleep(1)
    turn_motor_right(0)
    sleep(1)
    relax("left_muscle")
    sleep(1)
    turn_motor_left(SPEED)
    sleep(1)
    turn_motor_left(0)
    sleep(1)


if __name__ == "__main__":
    logging.info("Initializing...")
    print("Initializing...")
    motor = setup()  # TODO: make motor not a global variable
    setup_pygame()  # global variables
    hydrate_screen()  # hydrate the screen
    print("Initialization complete!")
    main()
