import logging
import math
import threading
from asyncio import sleep
from time import monotonic
from typing import ClassVar

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.parameter import Parameter
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Center, Grid, Horizontal, Vertical
from textual.widgets import Footer, Header, LoadingIndicator, RichLog, Static
from watchdog.observers import Observer, ObserverType

from .asset import (
    CAT,
    DOWN_ARROW,
    LEFT_ARROW,
    MDRC,
    RIGHT_ARROW,
    UP_ARROW,
)
from .component.motionsettings import MotionSettings
from .component.reactivebutton import ReactiveButton
from .utils.interval import (
    clear_all,
    clear_intervals,
    clear_timeouts,
    set_interval,
    set_timeout,
)

logger = logging.getLogger(__name__)
from .utils.logger import (
    LogHandler,
)

COMMAND_TOPIC = "/policy/cmd_vel"
DEFAULT_FORWARD_SPEED_MPS = 0.2
DEFAULT_LATERAL_SPEED_MPS = 0.2
DEFAULT_SPEED_GAIN = 1.0
DEFAULT_FAST_SPEED_MULTIPLIER = 3.0
DEFAULT_COMMAND_ACCELERATION_MPS2 = 1.0

pub_node: "PublishInput" = None
rosThread: threading.Thread = None


class PublishInput(Node):
    """Publish policy velocity commands from UI input."""

    def __init__(self, node_name="ui_node"):
        super().__init__(node_name)
        self.declare_parameter("forward_speed_mps", DEFAULT_FORWARD_SPEED_MPS)
        self.declare_parameter("lateral_speed_mps", DEFAULT_LATERAL_SPEED_MPS)
        self.declare_parameter("speed_gain", DEFAULT_SPEED_GAIN)
        self.declare_parameter(
            "command_acceleration_mps2", DEFAULT_COMMAND_ACCELERATION_MPS2
        )
        self.declare_parameter(
            "fast_speed_multiplier", DEFAULT_FAST_SPEED_MULTIPLIER
        )
        self.command_publisher = self.create_publisher(Twist, COMMAND_TOPIC, 10)
        self.last_velocity = (0.0, 0.0)
        self.last_velocity_time = monotonic()

    def _positive_parameter(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
        return value

    def publish_command(
        self,
        forward_direction: float = 0.0,
        left_direction: float = 0.0,
        *,
        fast: bool = False,
    ) -> None:
        """Publish normalized directions using the current velocity parameters."""
        gain = self._positive_parameter("speed_gain")
        multiplier = (
            self._positive_parameter("fast_speed_multiplier") if fast else 1.0
        )
        target = (
            forward_direction
            * self._positive_parameter("forward_speed_mps")
            * gain
            * multiplier,
            left_direction
            * self._positive_parameter("lateral_speed_mps")
            * gain
            * multiplier,
        )
        now = monotonic()
        max_change = self._positive_parameter("command_acceleration_mps2") * max(
            now - self.last_velocity_time, 0.0
        )
        delta = tuple(
            desired - current
            for current, desired in zip(self.last_velocity, target)
        )
        delta_magnitude = math.hypot(*delta)
        scale = min(1.0, max_change / delta_magnitude) if delta_magnitude else 1.0
        limited = tuple(
            current + change * scale
            for current, change in zip(self.last_velocity, delta)
        )
        self.last_velocity = limited
        self.last_velocity_time = now
        self.publish_direction(*limited)

    def stop(self) -> None:
        """Publish an immediate zero command and reset acceleration limiting."""
        self.last_velocity = (0.0, 0.0)
        self.last_velocity_time = monotonic()
        self.publish_direction()

    def update_motion_settings(
        self,
        forward_speed_mps: float,
        lateral_speed_mps: float,
        speed_gain: float,
        command_acceleration_mps2: float,
    ) -> None:
        """Apply validated UI values to the node's live ROS parameters."""
        values = {
            "forward_speed_mps": forward_speed_mps,
            "lateral_speed_mps": lateral_speed_mps,
            "speed_gain": speed_gain,
            "command_acceleration_mps2": command_acceleration_mps2,
        }
        for name, value in values.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        results = self.set_parameters(
            [Parameter(name, value=value) for name, value in values.items()]
        )
        if not all(result.successful for result in results):
            reasons = [result.reason for result in results if not result.successful]
            raise ValueError("; ".join(reasons) or "ROS rejected motion settings")

    def publish_direction(
        self,
        forward_mps: float = 0.0,
        left_mps: float = 0.0,
        yaw_radps: float = 0.0,
    ) -> None:
        message = Twist()
        message.linear.x = forward_mps
        message.linear.y = left_mps
        message.angular.z = yaw_radps
        self.command_publisher.publish(message)


class DirectionController:
    @staticmethod
    def _publish(
        forward_direction: float = 0.0,
        left_direction: float = 0.0,
        *,
        fast: bool = False,
    ) -> None:
        if pub_node is None:
            raise RuntimeError("UI ROS publisher is not initialized")
        try:
            pub_node.publish_command(
                forward_direction, left_direction, fast=fast
            )
        except ValueError as error:
            logger.error("Rejected UI speed configuration: %s", error)

    @staticmethod
    def left():
        logger.info("Left")
        DirectionController._publish(left_direction=1.0)

    @staticmethod
    def bigLeft():
        logger.info("Left")
        DirectionController._publish(left_direction=1.0, fast=True)

    @staticmethod
    def right():
        logger.info("Right")
        DirectionController._publish(left_direction=-1.0)

    @staticmethod
    def bigRight():
        logger.info("Right")
        DirectionController._publish(left_direction=-1.0, fast=True)

    @staticmethod
    def up():
        logger.info("Up")
        DirectionController._publish(forward_direction=1.0)

    @staticmethod
    def bigUp():
        logger.info("Up")
        DirectionController._publish(forward_direction=1.0, fast=True)

    @staticmethod
    def down():
        logger.info("Down")
        DirectionController._publish(forward_direction=-1.0)

    @staticmethod
    def bigDown():
        logger.info("Down")
        DirectionController._publish(forward_direction=-1.0, fast=True)

    @staticmethod
    def space():
        DirectionController.stop()

    @staticmethod
    def end_space():
        DirectionController.stop()

    @staticmethod
    def stop():
        logger.info("Stop")
        if pub_node is None:
            raise RuntimeError("UI ROS publisher is not initialized")
        pub_node.stop()


class Main_UI(App):

    file_observer: ObserverType

    CSS_PATH = "index.tcss"
    BINDINGS: ClassVar = [
        ("h", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
    ]

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
            if pub_node is None:
                raise RuntimeError("UI ROS publisher is not initialized")
            yield MotionSettings(
                pub_node._positive_parameter("forward_speed_mps"),
                pub_node._positive_parameter("lateral_speed_mps"),
                pub_node._positive_parameter("speed_gain"),
                pub_node._positive_parameter("command_acceleration_mps2"),
            )
            yield RichLog(id="log", highlight=True)
        yield Footer()

    def action_toggle_dark(self):
        self.dark = not self.dark

    def action_quit(self):
        DirectionController.stop()
        rclpy.shutdown()
        clear_all()
        self.exit()

    def on_ready(self):
        self.logger = self.query_one(RichLog)

        self.file_observer = Observer()
        log_handler = LogHandler(self.logger, self.file_observer)
        self.file_observer.schedule(log_handler, ".log", recursive=True)
        self.file_observer.start()

        sleep(0.8)
        self.query_one("#mdrc").styles.display = "none"
        self.query_one("#controller").styles.display = "block"
        self.query_one("#motion-settings").styles.display = "block"

    def clean_up(self):
        self.file_observer.stop()
        self.file_observer.join()

    @on(MotionSettings.Changed)
    def update_motion_settings(self, event: MotionSettings.Changed) -> None:
        if pub_node is None:
            raise RuntimeError("UI ROS publisher is not initialized")
        try:
            pub_node.update_motion_settings(
                event.forward_speed_mps,
                event.lateral_speed_mps,
                event.speed_gain,
                event.command_acceleration_mps2,
            )
        except ValueError as error:
            logger.error("Unable to apply motion settings: %s", error)
            return
        logger.info(
            "Applied motion settings: forward=%g m/s lateral=%g m/s "
            "gain=%g acceleration=%g m/s²",
            event.forward_speed_mps,
            event.lateral_speed_mps,
            event.speed_gain,
            event.command_acceleration_mps2,
        )

    @on(ReactiveButton.Active, "#up")
    async def action_up(self):
        logger.debug("Button up")
        DirectionController.up()
        self.upInterval = set_interval(DirectionController.up, 0.02)

    @on(ReactiveButton.Active, "#left")
    def action_left(self):
        logger.debug("Button left")
        DirectionController.left()
        self.leftInterval = set_interval(DirectionController.left, 0.02)

    @on(ReactiveButton.Active, "#middle")
    def action_middle(self):
        logger.debug("Button middle")
        DirectionController.space()

    @on(ReactiveButton.Active, "#right")
    def action_right(self):
        logger.debug("Button right")
        DirectionController.right()
        self.rightInterval = set_interval(DirectionController.right, 0.02)

    @on(ReactiveButton.Active, "#down")
    def action_down(self):
        logger.debug("Button down")
        DirectionController.down()
        self.downInterval = set_interval(DirectionController.down, 0.02)

    @on(ReactiveButton.Released, "#up")
    def action_up_end(self):
        logger.debug("Button up released")
        clear_intervals()
        DirectionController.stop()

    @on(ReactiveButton.Released, "#left")
    def action_left_end(self):
        logger.debug("Button left released")
        clear_intervals()
        DirectionController.stop()

    @on(ReactiveButton.Released, "#middle")
    def action_middle_end(self):
        logger.debug("Button middle released")
        DirectionController.end_space()

    @on(ReactiveButton.Released, "#right")
    def action_right_end(self):
        logger.debug("Button right released")
        clear_intervals()
        DirectionController.stop()

    @on(ReactiveButton.Released, "#down")
    def action_down_end(self):
        logger.debug("Button down released")
        clear_intervals()
        DirectionController.stop()

    def on_key(self, event: events.Key) -> None:
        match event.key:
            case "up" | "w":
                DirectionController.up()
            case "left" | "a":
                DirectionController.left()
            case "space":
                DirectionController.space()
            case "right" | "d":
                DirectionController.right()
            case "down" | "s":
                DirectionController.down()
            case _:
                return
        clear_timeouts()
        self.debouncedMiddle = set_timeout(DirectionController.stop, 0.15)


def main(args=None):
    global pub_node, rosThread
    rclpy.init(args=args)

    pub_node = PublishInput()
    rosThread = threading.Thread(target=lambda: rclpy.spin(pub_node))
    app = Main_UI()

    try:
        rosThread.start()
        app.run()
    except Exception:
        clear_all()
        app.clean_up()
        raise
    clear_all()
    app.clean_up()


if __name__ == "__main__":
    main()
