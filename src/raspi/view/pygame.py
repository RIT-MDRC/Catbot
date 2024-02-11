import logging

import pygame

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
"""Colors for pygame"""

GLOBAL_STORE = dict()


def setup_pygame():
    """Setup pygame"""
    pygame.init()
    GLOBAL_STORE["sysFont"] = pygame.font.SysFont("Ariel", 36)
    GLOBAL_STORE["screen"] = pygame.display.set_mode((640, 480))
    GLOBAL_STORE["clock"] = pygame.time.Clock()
    logging.info("Initialized global variabled: Font, Screen, Clock")
    GLOBAL_STORE["screen"].fill(WHITE)


def clock_tick(fps: int):
    """Ticks the clock

    Args:
        fps(int): the frames per second
    """
    GLOBAL_STORE["clock"].tick(fps)


def render_text(rect, text):
    """Renders a text on the screen

    Args:
        rect([int,int,int,int]): the rectangle to render the text in
        text(str): the text to render

    Returns:
        the rectangle of the rendered text
    """
    screen = GLOBAL_STORE["screen"]
    font = GLOBAL_STORE["sysFont"]
    screen.fill(WHITE, rect)
    surface = font.render(text, True, BLACK)
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


def get_keys():
    return pygame.event.get()


def update_screen():
    pygame.display.update()


def quit_pygame():
    pygame.quit()


TYPES = {
    "down": pygame.KEYDOWN,
    "up": pygame.KEYUP,
    "quit": pygame.QUIT,
}

KEYS = {
    "q": pygame.K_q,
    "w": pygame.K_w,
    "a": pygame.K_a,
    "d": pygame.K_d,
    "t": pygame.K_t,
    "up": pygame.K_UP,
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "down": pygame.K_DOWN,
}


def is_event_type(event, event_type: str):
    return event.type == TYPES[event_type]


def is_key_pressed(event, key: list[str]):
    keys = map(lambda k: KEYS[k], key)
    return event.key in keys
