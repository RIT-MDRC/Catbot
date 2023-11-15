from control.muscle.muscle_controller import contract, relax
from utils.interval import clear_intervals
from utils.util import *
from io_controller.pneumatics.pressure import on_pressure_active, on_pressure_deactive
import pygame

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
global sysFont
global screen
global clock


def setup():
    data = get_pinconfig()
    set_pin(data)
    pygame.init()
    sysFont = pygame.font.SysFont("Ariel", 36)
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    return sysFont, screen, clock


def main():
    screen.fill(WHITE)

    render_pressure_status(False)
    render_up_status(False)
    pygame.display.update()

    on_pressure_active(
        "left_pressure",
        lambda: render_pressure_status(True),
    )
    on_pressure_deactive(
        "left_pressure",
        lambda: render_pressure_status(False),
    )
    exit = False
    while not exit:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    exit = True
                elif event.key == pygame.K_w or event.key == pygame.K_UP:
                    contract("left_muscle")
                    render_up_status(True)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_w or event.key == pygame.K_UP:
                    relax("left_muscle")
                    render_up_status(False)
            elif event.type == pygame.QUIT:
                exit = True
        pygame.display.update()
        clock.tick(60)
    pygame.quit()
    clear_intervals()


def render_up_status(status: bool):
    screen.fill(WHITE, (0, 0, 640, 36))
    surface = sysFont.render(f"Up: {status}", True, BLACK)
    return screen.blit(surface, (0, 0))


def render_pressure_status(status: bool):
    screen.fill(WHITE, (0, 36, 640, 36))
    surface = sysFont.render(f"Pressure: {status}", True, BLACK)
    return screen.blit(surface, (0, 36))


sysFont, screen, clock = setup()
main()
