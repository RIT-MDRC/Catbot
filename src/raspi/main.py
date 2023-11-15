import curses
from curses import wrapper
from control.muscle.muscle_controller import contract, relax
from util import *
from io_controller.pneumatics.pressure import on_pressure_active, on_pressure_deactive
import pygame


def setup():
    data = get_pinconfig()
    set_pin(data)
    pygame.init()


def main():
    # on_pressure_active("left_pressure", lambda: updatePressureStatus(counter_win, True))
    # on_pressure_deactive(
    #     "left_pressure", lambda: updatePressureStatus(counter_win, False)
    # )
    screen = pygame.display.set_mode((640, 480))
    screen.fill((255, 255, 255))
    sysFont = pygame.font.SysFont("Ariel", 36)
    pygame.time.set_timer(pygame.USEREVENT + 1, 1000 // 30)

    def renderText(text: str, location: (int, int)):
        surface = sysFont.render(text, True, (0, 128, 0))
        screen.blit(surface, location)

    renderText("Up: False", (0, 0))
    exit = False
    while not exit:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    exit = True
                elif event.key == pygame.K_w:
                    screen.fill((255, 255, 255))
                    contract("left_muscle")
                    renderText("Up: True", (0, 0))
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_w:
                    screen.fill((255, 255, 255))
                    relax("left_muscle")
                    renderText("Up: False", (0, 0))
            elif event.type == pygame.QUIT:
                exit = True
        pygame.display.update()
    pygame.quit()


setup()
main()
