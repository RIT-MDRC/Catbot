from enum import Enum
from control.muscle.muscle_controller import contract, relax
from io_controller.pneumatics.compressor import (
    turn_compressor_off,
    turn_compressor_on,
)
from control.motor.motor_controller import MotorController
from utils.cpu import setup_cpu
from utils.interval import clear_intervals
from utils.util import *
from io_controller.pneumatics.pressure import on_pressure_active, on_pressure_deactive
import pygame

SPEED = 0.1


class Direction(Enum):
    FORWARD = 1
    BACKWARD = 0


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
    motor = MotorController(26, 0)

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
                elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
                    res = relax("left_muscle")
                    if res:
                        render_up_status(False)
                elif event.key == pygame.K_a or event.key == pygame.K_LEFT:
                    res = motor.set_Motor(SPEED, 1)
                    if res:
                        render_left_status(True)
                elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                    res = motor.set_Motor(SPEED, 0)
                    if res:
                        render_right_status(True)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_a or event.key == pygame.K_LEFT:
                    res = motor.set_Motor(0, 1)
                    if res:
                        render_left_status(False)
                elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                    res = motor.set_Motor(0, 0)
                    if res:
                        render_right_status(False)
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


sysFont, screen, clock, motor = setup()
main()
