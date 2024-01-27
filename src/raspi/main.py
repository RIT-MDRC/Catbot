from time import sleep
from control.muscle.muscle_controller import contract, relax
from io_controller.pneumatics.compressor import (
    turn_compressor_off,
    turn_compressor_on,
)
from control.motor.motor_controller import MotorController
from utils.cpu import setup_cpu
from utils.interval import clear_intervals
from utils.util import *
from io_controller.pneumatics.pressure import (
    is_pressure_ok,
    on_pressure_active,
    on_pressure_deactive,
)
import pygame

SPEED = 0.1

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
"""Colors for pygame"""

global sysFont, screen, clock, motor
"""Global variables for pygame"""


def setup():
    """Setup the pins and pygame"""
    data = get_pinconfig()
    set_pin(data)

    pygame.init()
    sysFont = pygame.font.SysFont("Ariel", 36)
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    motor = MotorController(26, 0, 1, [5, 6, 12])

    return sysFont, screen, clock, motor


def screen_setup():
    """Post setup for the screen (after pygame.init() and global variable are set)"""
    screen.fill(WHITE)
    render_pressure_status(False)
    render_up_status(False)
    render_left_status(False)
    render_right_status(False)
    render_temperature_status(0)
    pygame.display.update()


def main():
    """Main program loop"""
    screen_setup()
    setup_cpu(render_temperature_status)
    if is_pressure_ok("left_pressure"):
        change_compressor(True)
    on_pressure_active(
        "left_pressure",
        lambda: change_compressor(True),
    )
    on_pressure_deactive(
        "left_pressure",
        lambda: change_compressor(False),
    )
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
        clock.tick(60)
    pygame.quit()
    clear_intervals()


def render_text(rect, text):
    """Renders a text on the screen

    Args:
        rect([int,int,int,int]): the rectangle to render the text in
        text(str): the text to render

    Returns:
        the rectangle of the rendered text
    """
    screen.fill(WHITE, rect)
    surface = sysFont.render(text, True, BLACK)
    return screen.blit(surface, (rect[0], rect[1]))


def render_up_status(status: bool):
    """Renders the up button status

    Args:
        status(bool): the status to render
    """
    render_text((0, 0, 640, 36), f"Up: {status}")


def render_pressure_status(status: bool):
    """Renders the pressure status

    Args:
        status(bool): the status to render
    """
    render_text((0, 36, 640, 36), f"Pressure: {status}")


def render_left_status(status: bool):
    """Renders the left button status

    Args:
        status(bool): the status to render
    """
    render_text((0, 72, 640, 36), f"Left: {status}")


def render_right_status(status: bool):
    """Renders the right button status

    Args:
        status(bool): the status to render
    """
    render_text((0, 108, 640, 36), f"Right: {status}")


def render_temperature_status(temperature: float):
    """Renders the temperature status

    Args:
        temperature(float): the temperature to render
    """
    render_text((0, 144, 640, 36), f"Temperature: {temperature}")


def change_compressor(status: bool):
    """Renders the compressor status

    Args:
        status(bool): the status to render
    """
    action = turn_compressor_on if status else turn_compressor_off
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


sysFont, screen, clock, motor = setup()
main()
