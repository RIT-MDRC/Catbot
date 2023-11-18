from control.muscle.muscle_controller import contract, relax, toggle_muscle_state
from io_controller.pneumatics.compressor import (
    turn_compressor_off,
    turn_compressor_on,
)
from utils.interval import clear_intervals
from utils.util import *
from io_controller.pneumatics.pressure import on_pressure_active, on_pressure_deactive
import pygame

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
"""Colors for pygame"""

global sysFont, screen, clock
"""Global variables for pygame"""


def setup():
    """Setup the pins and pygame"""
    data = get_pinconfig()
    set_pin(data)

    pygame.init()
    sysFont = pygame.font.SysFont("Ariel", 36)
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()

    return sysFont, screen, clock


def screen_setup():
    """Post setup for the screen (after pygame.init() and global variable are set)"""
    screen.fill(WHITE)
    render_pressure_status(False)
    render_up_status(False)
    pygame.display.update()


def main():
    """Main program loop"""
    screen_setup()

    on_pressure_active(
        "left_pressure",
        lambda: render_pressure_status(False),
    )
    on_pressure_deactive(
        "left_pressure",
        lambda: render_pressure_status(True),
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
            elif event.type == pygame.KEYUP:
                pass
                # if event.key == pygame.K_w or event.key == pygame.K_UP:
                #     res = toggle_muscle_state("left_muscle")
                #     if res:
                #         render_up_status(False)
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


def change_compressor(status: bool):
    """Renders the compressor status

    Args:
        status(bool): the status to render
    """
    action = turn_compressor_on if status else turn_compressor_off
    action("main_compressor")


sysFont, screen, clock = setup()
main()
