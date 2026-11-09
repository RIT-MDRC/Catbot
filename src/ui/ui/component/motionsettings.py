"""Runtime motion-setting controls for the Catbot UI."""

import math

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Input, Static


class MotionSettings(Vertical):
    """Edit policy velocity and acceleration settings while the UI is running."""

    class Changed(Message):
        def __init__(
            self,
            forward_speed_mps: float,
            lateral_speed_mps: float,
            speed_gain: float,
            command_acceleration_mps2: float,
        ) -> None:
            super().__init__()
            self.forward_speed_mps = forward_speed_mps
            self.lateral_speed_mps = lateral_speed_mps
            self.speed_gain = speed_gain
            self.command_acceleration_mps2 = command_acceleration_mps2

    def __init__(
        self,
        forward_speed_mps: float,
        lateral_speed_mps: float,
        speed_gain: float,
        command_acceleration_mps2: float,
    ) -> None:
        super().__init__(id="motion-settings")
        self.initial_values = {
            "forward-speed": forward_speed_mps,
            "lateral-speed": lateral_speed_mps,
            "speed-gain": speed_gain,
            "command-acceleration": command_acceleration_mps2,
        }

    def compose(self) -> ComposeResult:
        yield Static("Motion settings", id="motion-settings-title")
        yield Static("Forward speed (m/s)", classes="motion-label")
        yield Input(
            value=str(self.initial_values["forward-speed"]),
            type="number",
            id="forward-speed",
        )
        yield Static("Lateral speed (m/s)", classes="motion-label")
        yield Input(
            value=str(self.initial_values["lateral-speed"]),
            type="number",
            id="lateral-speed",
        )
        yield Static("Speed gain", classes="motion-label")
        yield Input(
            value=str(self.initial_values["speed-gain"]),
            type="number",
            id="speed-gain",
        )
        yield Static("Acceleration (m/s²)", classes="motion-label")
        yield Input(
            value=str(self.initial_values["command-acceleration"]),
            type="number",
            id="command-acceleration",
        )
        yield Button("Apply", id="apply-motion-settings", variant="primary")
        yield Static("", id="motion-settings-status")

    def _positive_value(self, input_id: str) -> float:
        value = float(self.query_one(f"#{input_id}", Input).value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("all motion settings must be finite and positive")
        return value

    @on(Button.Pressed, "#apply-motion-settings")
    def apply(self) -> None:
        status = self.query_one("#motion-settings-status", Static)
        try:
            values = {
                "forward_speed_mps": self._positive_value("forward-speed"),
                "lateral_speed_mps": self._positive_value("lateral-speed"),
                "speed_gain": self._positive_value("speed-gain"),
                "command_acceleration_mps2": self._positive_value(
                    "command-acceleration"
                ),
            }
        except ValueError as error:
            status.update(str(error))
            status.add_class("error")
            return
        status.remove_class("error")
        status.update("Applied")
        self.post_message(self.Changed(**values))
