import logging
from logging import LogRecord
from time import sleep

from state_management.device import configure_device
from state_management.utils.logger import configure_logger, set_log_event_function
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Center, Grid, Horizontal, Vertical
from textual.widgets import Footer, Header, LoadingIndicator, RichLog, Static
from view.textualUI.asset import DOWN_ARROW, LEFT_ARROW, MDRC, RIGHT_ARROW, UP_ARROW
from view.textualUI.reactivebutton import ReactiveButton


class Main_UI(App):

    CSS_PATH = "index.tcss"
    BINDINGS = [("h", "toggle_dark", "Toggle dark mode"), ("q", "quit", "Quit")]

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
                    variant="primary",
                )
                yield Static(id="rt")
                yield ReactiveButton(
                    LEFT_ARROW,
                    on_blur=button_blur,
                    id="left",
                    variant="primary",
                )
                yield ReactiveButton(
                    "O", on_blur=button_blur, id="middle", variant="primary"
                )
                yield ReactiveButton(
                    RIGHT_ARROW,
                    on_blur=button_blur,
                    id="right",
                    variant="primary",
                )
                yield Static(id="lb")
                yield ReactiveButton(
                    DOWN_ARROW,
                    on_blur=button_blur,
                    id="down",
                    variant="primary",
                )
                yield Static(id="rb")
            yield RichLog(id="log", highlight=True)
        yield Footer()

    def action_toggle_dark(self):
        self.dark = not self.dark

    def action_quit(self):
        self.exit()

    def on_ready(self):
        configure_logger()
        self.logger = self.query_one(RichLog)

        def log_event(event: LogRecord):
            self.logger.write(f"{event.filename}:{event.msg % event.args}")
            return True

        set_log_event_function(log_event)

        configure_device("src/raspi/pinconfig.json")
        logging.info("Initialized components from pinconfig")
        sleep(1)
        self.query_one("#mdrc").styles.display = "none"
        self.query_one("#controller").styles.display = "block"

    @on(ReactiveButton.Active, "#up")
    def action_up(self):
        logging.debug("Button up")

    @on(ReactiveButton.Active, "#left")
    def action_left(self):
        logging.debug("Button left")

    @on(ReactiveButton.Active, "#middle")
    def action_middle(self):
        logging.debug("Button middle")

    @on(ReactiveButton.Active, "#right")
    def action_right(self):
        logging.debug("Button right")

    @on(ReactiveButton.Active, "#down")
    def action_down(self):
        logging.debug("Button down")

    @on(ReactiveButton.Released, "#up")
    def action_up_end(self):
        logging.debug("Button up released")

    @on(ReactiveButton.Released, "#left")
    def action_left_end(self):
        logging.debug("Button left released")

    @on(ReactiveButton.Released, "#middle")
    def action_middle_end(self):
        logging.debug("Button middle released")

    @on(ReactiveButton.Released, "#right")
    def action_right_end(self):
        logging.debug("Button right released")

    @on(ReactiveButton.Released, "#down")
    def action_down_end(self):
        logging.debug("Button down released")


def setup_textual():
    Main_UI().run()


if __name__ == "__main__":
    setup_textual()
