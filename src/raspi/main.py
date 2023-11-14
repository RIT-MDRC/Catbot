import curses
from curses import wrapper
from util import *
from io_controller.pneumatics.pressure import on_pressure_active, on_pressure_deactive
import pygame


def setup():
    data = get_pinconfig()
    set_pin(data)


def main(stdscr):
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_RED)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    stdscr.clear()
    stdscr.refresh()

    counter_win = curses.newwin(50, 50, 0, 40)
    counter_win.nodelay(True)
    updatePressureStatus(counter_win, False)
    counter_win.refresh()
    on_pressure_active("left_pressure", lambda: updatePressureStatus(counter_win, True))
    on_pressure_deactive(
        "left_pressure", lambda: updatePressureStatus(counter_win, False)
    )
    exit = False
    while not exit:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            exit = True
            continue


def updatePressureStatus(win, bool):
    RED_BLACK = curses.color_pair(1)
    BLACK_WHITE = curses.color_pair(2)
    win.addstr("Pressure: " + str(bool), BLACK_WHITE if bool else RED_BLACK)
    win.refresh()


setup()
wrapper(main)
