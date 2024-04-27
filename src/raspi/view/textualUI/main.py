import logging
import threading
from asyncio import sleep
from logging import LogRecord

from component.latch import latch_actions
from component.motor import raw_motor_action
from component.muscle import muscle_actions
from state_management import configure_device
from state_management.utils.interval import (
    clear_all,
    clear_intervals,
    clear_timeouts,
    set_interval,
    set_timeout,
)
from state_management.utils.logger import set_log_event_function
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Center, Grid, Horizontal, Vertical
from textual.widgets import Footer, Header, LoadingIndicator, RichLog, Static
from view.textualUI.asset import (
    CAT,
    DOWN_ARROW,
    LEFT_ARROW,
    MDRC,
    RIGHT_ARROW,
    UP_ARROW,
)
from view.textualUI.reactivebutton import ReactiveButton

latch_actions.USE = True

MUSCLE = "left_muscle"

LATERAL_MOTOR = "motor_1"
MEDIAL_MOTOR = "motor_2"
LEFT_DISTANCE = 2
RIGHT_DISTANCE = -2
MULTIPLIER = 8


class DirectionController:
    @staticmethod
    def left():
        logging.info("Left")
        raw_motor_action.step_n(LATERAL_MOTOR, LEFT_DISTANCE)

    @staticmethod
    def bigLeft():
        logging.info("Left")
        raw_motor_action.step_n(LATERAL_MOTOR, LEFT_DISTANCE * MULTIPLIER)

    @staticmethod
    def right():
        logging.info("Right")
        raw_motor_action.step_n(LATERAL_MOTOR, RIGHT_DISTANCE)

    @staticmethod
    def bigRight():
        logging.info("Right")
        raw_motor_action.step_n(LATERAL_MOTOR, RIGHT_DISTANCE * MULTIPLIER)

    @staticmethod
    def up():
        logging.info("Up")
        raw_motor_action.step_n(MEDIAL_MOTOR, LEFT_DISTANCE)

    @staticmethod
    def bigUp():
        logging.info("Up")
        raw_motor_action.step_n(MEDIAL_MOTOR, LEFT_DISTANCE * MULTIPLIER)

    @staticmethod
    def down():
        logging.info("Down")
        raw_motor_action.step_n(MEDIAL_MOTOR, RIGHT_DISTANCE)

    @staticmethod
    def bigDown():
        logging.info("Down")
        raw_motor_action.step_n(MEDIAL_MOTOR, RIGHT_DISTANCE * MULTIPLIER)

    @staticmethod
    def space():
        logging.info("Space")
        muscle_actions.contract(MUSCLE, lambda _: True)

    @staticmethod
    def end_space():
        logging.info("End Space")
        muscle_actions.relax(MUSCLE, lambda _: True)
        raw_motor_action.step_n(MEDIAL_MOTOR, 1)
        raw_motor_action.step_n(MEDIAL_MOTOR, -1)


class Main_UI(App):

    CSS_PATH = "index.tcss"
    BINDINGS = [("h", "toggle_dark", "Toggle dark mode"), ("q", "quit", "Quit")]

    last_key = None

    leftInterval: threading.Timer = None
    rightInterval: threading.Timer = None
    upInterval: threading.Timer = None
    downInterval: threading.Timer = None

    debouncedMiddle: callable = None

    def compose(self) -> ComposeResult:
        def button_blur():
            self.query_one("#log").focus()

        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="mdrc"):
                with Center(id="center"):
                    yield Static(MDRC, id="logo")
                yield LoadingIndicator(MDRC, id="loading")
            with Grid(id="controller"):
                yield Static(id="lt")
                yield ReactiveButton(
                    UP_ARROW,
                    on_blur=button_blur,
                    id="up",
                )
                yield Static(id="rt")
                yield ReactiveButton(
                    LEFT_ARROW,
                    on_blur=button_blur,
                    id="left",
                )
                yield ReactiveButton(CAT, on_blur=button_blur, id="middle")
                yield ReactiveButton(
                    RIGHT_ARROW,
                    on_blur=button_blur,
                    id="right",
                )
                yield Static(id="lb")
                yield ReactiveButton(
                    DOWN_ARROW,
                    on_blur=button_blur,
                    id="down",
                )
                yield Static(id="rb")
            yield RichLog(id="log", highlight=True)
        yield Footer()

    def action_toggle_dark(self):
        self.dark = not self.dark

    def action_quit(self):
        clear_all()
        self.exit()

    def on_ready(self):
        self.logger = self.query_one(RichLog)

        def log_event(event: LogRecord):
            self.logger.write(f"{event.filename}:{event.msg % event.args}")
            return True

        set_log_event_function(log_event)

        logging.info("Initialized components from pinconfig")
        sleep(1)
        self.query_one("#mdrc").styles.display = "none"
        self.query_one("#controller").styles.display = "block"

    @on(ReactiveButton.Active, "#up")
    async def action_up(self):
        logging.debug("Button up")
        DirectionController.up()
        self.upInterval = set_interval(DirectionController.up, 0.02)

    @on(ReactiveButton.Active, "#left")
    def action_left(self):
        logging.debug("Button left")
        DirectionController.left()
        self.leftInterval = set_interval(DirectionController.left, 0.02)

    @on(ReactiveButton.Active, "#middle")
    def action_middle(self):
        logging.debug("Button middle")
        DirectionController.space()

    @on(ReactiveButton.Active, "#right")
    def action_right(self):
        logging.debug("Button right")
        DirectionController.right()
        self.rightInterval = set_interval(DirectionController.right, 0.02)

    @on(ReactiveButton.Active, "#down")
    def action_down(self):
        logging.debug("Button down")
        DirectionController.down()
        self.downInterval = set_interval(DirectionController.down, 0.02)

    @on(ReactiveButton.Released, "#up")
    def action_up_end(self):
        logging.debug("Button up released")
        clear_intervals()

    @on(ReactiveButton.Released, "#left")
    def action_left_end(self):
        logging.debug("Button left released")
        clear_intervals()

    @on(ReactiveButton.Released, "#middle")
    def action_middle_end(self):
        logging.debug("Button middle released")
        DirectionController.end_space()

    @on(ReactiveButton.Released, "#right")
    def action_right_end(self):
        logging.debug("Button right released")
        clear_intervals()

    @on(ReactiveButton.Released, "#down")
    def action_down_end(self):
        logging.debug("Button down released")
        clear_intervals()

    def on_key(self, event: events.Key) -> None:
        if self.last_key != event.key:
            match event.key:
                case "up" | "w":
                    DirectionController.bigUp()
                case "left" | "a":
                    DirectionController.bigLeft()
                case "right" | "d":
                    DirectionController.bigRight()
                case "down" | "s":
                    DirectionController.bigDown()
                case "space":
                    DirectionController.space()
                case _:
                    pass
            self.last_key = event.key
            return
        match event.key:
            case "up" | "w":
                DirectionController.up()
            case "left" | "a":
                DirectionController.left()
            case "space":

                def end_space_callback():
                    self.debouncedMiddle = None
                    DirectionController.end_space()

                if self.debouncedMiddle:
                    clear_timeouts()
                    self.debouncedMiddle = set_timeout(end_space_callback, 0.5)
                    pass

                DirectionController.space()
                self.debouncedMiddle = set_timeout(end_space_callback, 0.5)
            case "right" | "d":
                DirectionController.right()
            case "down" | "s":
                DirectionController.down()
            case _:
                pass


def main():
    try:
        Main_UI().run()
    except Exception as e:
        clear_all()
        raise


if __name__ == "__main__":
    configure_device("src/raspi/pinconfig.json")
    main()
