"""Interactively command configured ODrive motors by joint angle."""

import argparse
import math
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import ClassVar

from motor_test_errors import MotorTestErrors as Errors
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static, TextArea

# Direct script execution needs Foundation on the module search path.
FOUNDATION_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.fspath(FOUNDATION_ROOT))

# Component imports register device parsers before configure_device is called.
from component.actuator import actuator_actions
from component.can import can_actions
from component.motor import motor_actions
from component.motor.odrive_enums import MotorState
from state_management import configure_device

HEARTBEAT_TIMEOUT_SECONDS = 3.0

DEFAULT_CONFIG = Path(__file__).with_name("demo_config.json")
FAULT_DETAIL_NAMES = ("motor", "encoder", "sensorless", "controller")
QUIT_COMMANDS = frozenset({"q", "quit", "exit"})
POSITION_COMMANDS = frozenset({"mp", "mr"})
HISTORY_KEYS = frozenset({"up", "down"})

COMMAND_HANDLERS = {
    "arm": "_arm",
    "a": "_arm",
    "disarm": "_disarm",
    "d": "_disarm",
    "r": "_read_position",
    "read": "_read_position",
    "rs": "_read_speed",
    "read-speed": "_read_speed",
    "e": "_clear_errors",
    "clear": "_clear_errors",
}
SHORTCUT_STATES = {
    "c": ("motor calibration", MotorState.MOTOR_CALIBRATION),
    "calibrate": ("motor calibration", MotorState.MOTOR_CALIBRATION),
    "f": ("full calibration", MotorState.FULL_CALIBRATION_SEQUENCE),
    "full": ("full calibration", MotorState.FULL_CALIBRATION_SEQUENCE),
    "full-calibration": ("full calibration", MotorState.FULL_CALIBRATION_SEQUENCE),
    "h": ("homing", MotorState.HOMING),
    "home": ("homing", MotorState.HOMING),
}
AXIS_ERROR_NAMES = {
    0x1: "INVALID_STATE",
    0x40: "MOTOR_FAILED",
    0x80: "SENSORLESS_ESTIMATOR_FAILED",
    0x100: "ENCODER_FAILED",
    0x200: "CONTROLLER_FAILED",
    0x800: "WATCHDOG_TIMER_EXPIRED",
    0x1000: "MIN_ENDSTOP_PRESSED",
    0x2000: "MAX_ENDSTOP_PRESSED",
    0x4000: "ESTOP_REQUESTED",
    0x20000: "HOMING_WITHOUT_ENDSTOP",
    0x40000: "OVER_TEMP",
    0x80000: "UNKNOWN_POSITION",
}
AXIS_ERROR_KNOWN_MASK = sum(AXIS_ERROR_NAMES)
ERROR_LOG_MARKERS = (
    "invalid command",
    "failed",
    "unable",
    "command rejected",
    "clear the error",
    "no heartbeat",
)
SUCCESS_LOG_MARKERS = ("armed ", "commanded ", "set ")

COMMAND_HELP = (
    "Commands: arm [motor[,motor...]], disarm [motor[,motor...]], "
    "r/read [motor[,motor...]] = read angle, "
    "speed <deg/s> [motor[,motor...]], "
    "rs/read-speed [motor[,motor...]], "
    "mp <angle> [motor[,motor...]] = absolute position, "
    "mr <angle> [motor[,motor...]] = relative motion, "
    "c [motor] = motor calibration, "
    "f [motor] = full calibration, h [motor] = home, "
    "e [motor] = clear errors, q = stop."
)


def motor_fault_values(motor) -> tuple[int, ...]:
    """Return all fault indicators exposed by heartbeat and detail messages."""
    return (
        getattr(motor, "axis_error", 0),
        getattr(motor, "motor_error", 0),
        getattr(motor, "encoder_error", 0),
        getattr(motor, "sensorless_error", 0),
        getattr(motor, "controller_error", 0),
        int(getattr(motor, "motor_error_flag", False)),
        int(getattr(motor, "encoder_error_flag", False)),
        int(getattr(motor, "sensorless_error_flag", False)),
        int(getattr(motor, "controller_error_flag", False)),
    )


def describe_motor_fault(values: tuple[int, ...]) -> str:
    """Format a compact summary of axis, detailed, and pending errors."""
    axis, motor, encoder, sensorless, controller, *flags = values
    parts = []
    if axis:
        parts.append(f"axis=0x{axis:x} {describe_axis_error(axis)}")
    details = (motor, encoder, sensorless, controller)
    for name, detail, flagged in zip(FAULT_DETAIL_NAMES, details, flags):
        if detail:
            parts.append(f"{name}=0x{detail:x}")
        elif flagged:
            parts.append(f"{name}=flagged")
    return ", ".join(parts)


def parse_speed_degrees_per_second(value: str) -> float:
    """Parse a finite, positive joint-speed limit."""
    speed = float(value)
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError(Errors.POSITIVE_SPEED_REQUIRED)
    return speed


def parse_angle_degrees(value: str) -> float:
    """Parse a finite joint-angle command."""
    angle_degrees = float(value)
    if not math.isfinite(angle_degrees):
        raise ValueError(Errors.FINITE_ANGLE_REQUIRED)
    return angle_degrees


def position_target_degrees(
    command: str, angle_degrees: float, current_degrees: float | None = None
) -> float:
    """Resolve an absolute or relative command to an absolute logical target."""
    if command == "mp":
        return angle_degrees
    if command == "mr":
        if current_degrees is None:
            raise ValueError(Errors.CURRENT_POSITION_REQUIRED)
        return current_degrees + angle_degrees
    raise ValueError(Errors.UNKNOWN_POSITION_COMMAND.format(command=command))


def parse_args() -> argparse.Namespace:
    """Parse motor-test command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Move configured homed ODrive motors to typed joint angles."
    )
    parser.add_argument(
        "--motor",
        help=(
            "configured motor name, CAN axis ID, comma-separated selection, "
            "or * for every motor"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"device configuration file (default: {DEFAULT_CONFIG})",
    )
    return parser.parse_args()


def describe_motors(motors) -> str:
    """List configured motor names and their CAN axis IDs."""
    return (
        ", ".join(
            f"{name} (axis {motor.axisID})" for name, motor in sorted(motors.items())
        )
        or "none"
    )


def find_motors(motors, selector: str | None):
    """Find motors by *, comma list, exact configured name, or CAN axis ID."""
    if selector is None:
        return []
    if "," in selector:
        selections = [selection.strip() for selection in selector.split(",")]
        if any(not selection for selection in selections):
            return []
        matches = []
        selected_names = set()
        for selection in selections:
            selection_matches = find_motors(motors, selection)
            if len(selection_matches) != 1:
                return []
            name, motor = selection_matches[0]
            if name not in selected_names:
                matches.append((name, motor))
                selected_names.add(name)
        return matches
    if selector == "*":
        return sorted(motors.items(), key=lambda item: (item[1].axisID, item[0]))
    if selector in motors:
        return [(selector, motors[selector])]
    try:
        axis_id = int(selector, 10)
    except ValueError:
        return []
    return [
        (name, motor)
        for name, motor in sorted(motors.items())
        if motor.axisID == axis_id
    ]


def describe_axis_error(error: int) -> str:
    """Decode an ODrive axis-error bitmask into a compact list of flag names."""
    decoded = []
    for flag, name in AXIS_ERROR_NAMES.items():
        if error & flag:
            decoded.append(name)
    unknown_bits = error & ~AXIS_ERROR_KNOWN_MASK
    if unknown_bits:
        decoded.append(f"UNKNOWN_BITS_0x{unknown_bits:x}")
    return f"[{', '.join(decoded)}]"


def is_multi_motor_selector(selector: str | None) -> bool:
    """Return whether a selector intentionally names multiple motors."""
    return selector == "*" or (selector is not None and "," in selector)


def report_bus_errors(motors, emit=print) -> bool:
    """Print every currently reported ODrive error on the configured CAN bus."""
    errors = [
        f"{name} (axis {motor.axisID}): 0x{motor.axis_error:x} "
        f"({describe_axis_error(motor.axis_error)})"
        for name, motor in sorted(motors.items())
        if motor.axis_error
    ]
    if not errors:
        return False
    emit(Errors.BUS_ERRORS)
    for error in errors:
        emit(f"  {error}")
    return True


def wait_for(motor_name, predicate, timeout: float, should_stop=None) -> bool:
    """Wait for asynchronous CAN feedback to satisfy a predicate."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if should_stop is not None and should_stop():
            return False
        if predicate(motor_actions.get_state_snapshot(motor_name)):
            return True
        time.sleep(0.05)
    return False


class MotorTestSession:
    """Keep command handling and armed-motor state for one configured session."""

    def __init__(self, motors, emit=print, should_stop=None):
        self.motors = motors
        self.motor_names = list(motors)
        self.emit = emit
        self.should_stop = should_stop
        self.default_motor_name = None
        self.active_motor_names: set[str] = set()

    def refresh_motors(self) -> None:
        """Read fresh snapshots before processing each command."""
        self.motors = {
            name: motor_actions.get_state_snapshot(name) for name in self.motor_names
        }

    def prepare(self, selector: str | None) -> int | None:
        """Return a startup status, or None if cancelled during heartbeat waits."""
        selected_motors = []
        if selector:
            matches = find_motors(self.motors, selector)
            if not matches or (
                len(matches) != 1 and not is_multi_motor_selector(selector)
            ):
                if matches and not is_multi_motor_selector(selector):
                    names = ", ".join(name for name, _ in matches)
                    self.emit(
                        Errors.AMBIGUOUS_AXIS.format(selector=selector, names=names)
                    )
                else:
                    self.emit(Errors.UNKNOWN_MOTOR.format(selector=selector))
                self.emit(f"Configured motors: {describe_motors(self.motors)}")
                return 2
            selected_motors = matches
            self.default_motor_name = selector
            if len(matches) == 1:
                self.default_motor_name = matches[0][0]
        else:
            self.emit(
                "No default motor selected; include a motor name or axis ID "
                "in commands."
            )
            self.emit(f"Configured motors: {describe_motors(self.motors)}")

        for selected_motor_name, _ in selected_motors:
            if self.should_stop is not None and self.should_stop():
                return None
            self.emit(f"Waiting for an ODrive heartbeat from {selected_motor_name}...")
            if not wait_for(
                selected_motor_name,
                lambda motor: motor.current_state != MotorState.UNDEFINED,
                HEARTBEAT_TIMEOUT_SECONDS,
                self.should_stop,
            ):
                if self.should_stop is not None and self.should_stop():
                    return None
                self.emit(Errors.NO_HEARTBEAT.format(name=selected_motor_name))
                self.emit(Errors.HEARTBEAT_HELP)
                return 3
        if selected_motors:
            self.refresh_motors()
            report_bus_errors(self.motors, self.emit)
            selected_names = ", ".join(name for name, _ in selected_motors)
            self.emit(f"{selected_names} disarmed; type 'arm' to enable the selection.")

        return 0

    def run(self, read_command) -> None:
        """Read and dispatch commands until quit or end of input."""
        while True:
            try:
                raw_value = read_command("angle> ").strip()
            except EOFError:
                return
            self.refresh_motors()
            if not self.execute_command(raw_value):
                return

    def execute_command(self, raw_value: str) -> bool:
        """Dispatch one command; return False when the session should exit."""
        parts = raw_value.split(maxsplit=1)
        if not parts:
            self.emit(Errors.EMPTY_COMMAND)
            return True
        command = parts[0].lower()
        arguments = parts[1] if len(parts) == 2 else ""
        if command in QUIT_COMMANDS:
            return False
        if command == "speed":
            self._set_speed(arguments)
            return True
        if command in POSITION_COMMANDS:
            self._move(command, arguments)
            return True

        if command not in COMMAND_HANDLERS and command not in SHORTCUT_STATES:
            self.emit(Errors.UNKNOWN_COMMAND)
            return True
        matches = self._select_motors(arguments or self.default_motor_name)
        if matches:
            if command in SHORTCUT_STATES:
                self._request_state(matches, *SHORTCUT_STATES[command])
            else:
                getattr(self, COMMAND_HANDLERS[command])(matches)
        return True

    def _select_motors(self, selector, position_command=None):
        """Validate a complete selection before executing any motor command."""
        matches = find_motors(self.motors, selector)
        if matches and (len(matches) == 1 or is_multi_motor_selector(selector)):
            return matches
        if position_command is None:
            self.emit(Errors.INVALID_MOTOR_SELECTION)
        else:
            self.emit(
                Errors.INVALID_POSITION_SELECTION.format(
                    position_command=position_command
                )
            )
        self.emit(f"Configured motors: {describe_motors(self.motors)}")
        return []

    def _read_position(self, matches) -> None:
        """Report cached joint position without arming."""

        for name, motor in matches:
            if motor.current_position is None:
                self.emit(Errors.NO_ENCODER_POSITION.format(name=name))
                continue
            angle_degrees = actuator_actions.get_current_position(name)
            self.emit(
                f"{name}: {angle_degrees:.2f} degrees "
                f"({motor.current_position:.4f} motor turns)."
            )

    def _read_speed(self, matches) -> None:
        """Report measured joint speed without changing its configured limit."""

        for name, motor in matches:
            if motor.current_velocity is None:
                self.emit(Errors.NO_ENCODER_SPEED.format(name=name))
                continue
            speed_degrees = actuator_actions.get_current_velocity(name)
            self.emit(
                f"{name}: {speed_degrees:.2f} degrees/second "
                f"({motor.current_velocity:.4f} motor turns/second)."
            )

    def _arm(self, matches) -> None:
        """Enable position control only after confirming a safe hold and heartbeat."""
        for name, motor in matches:
            if motor.axis_error:
                self.emit(Errors.FAULT_BEFORE_ARM.format(name=name))
                continue
            if motor.current_position is None:
                self.emit(Errors.NO_HOLD_POSITION.format(name=name))
                continue
            self.emit(Errors.ARM_WARNING.format(name=name))
            if not actuator_actions.configure_trajectory(name):
                self.emit(Errors.TRAJECTORY_FAILED.format(name=name))
                continue
            if not motor_actions.hold_current_position(name):
                self.emit(Errors.HOLD_FAILED.format(name=name))
                continue
            if not motor_actions.set_axis_state(name, MotorState.CLOSED_LOOP_CONTROL):
                self.emit(Errors.ARM_REQUEST_FAILED.format(name=name))
                continue
            if not wait_for(
                name,
                lambda motor: motor.current_state == MotorState.CLOSED_LOOP_CONTROL,
                HEARTBEAT_TIMEOUT_SECONDS,
                self.should_stop,
            ):
                self.emit(Errors.ARM_NOT_CONFIRMED.format(name=name))
                motor_actions.set_axis_state(name, MotorState.IDLE)
                continue
            self.active_motor_names.add(name)
            self.emit(f"Armed {name} in position control.")
        report_bus_errors(self.motors, self.emit)

    def _disarm(self, matches) -> None:
        """Request idle and remove confirmed disarmed motors from the active set."""
        for name, _ in matches:
            if not motor_actions.set_axis_state(name, MotorState.IDLE):
                self.emit(Errors.DISARM_REQUEST_FAILED.format(name=name))
                continue
            if not wait_for(
                name,
                lambda motor: motor.current_state == MotorState.IDLE,
                HEARTBEAT_TIMEOUT_SECONDS,
                self.should_stop,
            ):
                self.emit(Errors.DISARM_NOT_CONFIRMED.format(name=name))
                continue
            self.active_motor_names.discard(name)
            self.emit(f"Disarmed {name}.")

    def _clear_errors(self, matches) -> None:
        """Clear selected errors and report remaining bus faults."""
        for name, _ in matches:
            if motor_actions.clear_error_message(name):
                self.emit(f"Requested error clear for {name}.")
            else:
                self.emit(Errors.CLEAR_FAILED.format(name=name))
        time.sleep(0.2)
        report_bus_errors(self.motors, self.emit)

    def _request_state(self, matches, action_name, requested_state: MotorState) -> None:
        """Request calibration or homing for each selected motor."""
        self.emit(Errors.MOVEMENT_WARNING.format(action_name=action_name))
        for name, _ in matches:
            if motor_actions.set_axis_state(name, requested_state):
                self.emit(f"Requested {action_name} for {name}.")
            else:
                self.emit(
                    Errors.STATE_REQUEST_FAILED.format(
                        action_name=action_name, name=name
                    )
                )

    def _set_speed(self, arguments: str) -> None:
        """Parse and apply the trajectory speed limit for selected motors."""
        parts = arguments.split(maxsplit=1)
        try:
            speed_degrees = parse_speed_degrees_per_second(parts[0])
        except (IndexError, ValueError):
            self.emit(Errors.INVALID_SPEED)
            return
        selector = parts[1] if len(parts) == 2 else self.default_motor_name
        matches = self._select_motors(selector)
        for name, _ in matches:
            if actuator_actions.set_trajectory_speed(name, speed_degrees):
                speed_turns = actuator_actions.get_trajectory_velocity_motor_turns(name)
                self.emit(
                    f"Set {name} trajectory speed to "
                    f"{speed_degrees:g} degrees/second "
                    f"({speed_turns:.4f} motor turns/second)."
                )
            else:
                self.emit(Errors.SPEED_FAILED.format(name=name))

    def _move(self, command: str, arguments: str) -> None:
        """Resolve a finite angle and apply motion checks separately to each motor."""
        parts = arguments.split(maxsplit=1)
        try:
            angle_degrees = parse_angle_degrees(parts[0])
        except (IndexError, ValueError):
            self.emit(Errors.INVALID_ANGLE.format(command=command))
            return
        selector = parts[1] if len(parts) == 2 else self.default_motor_name
        matches = self._select_motors(selector, position_command=command)
        if not matches:
            return
        report_bus_errors(self.motors, self.emit)
        for name, motor in matches:
            self._move_motor(command, angle_degrees, name, motor)

    def _move_motor(self, command, angle_degrees, name, motor) -> None:
        """Validate arm state, relative feedback, and bounds before sending a target."""

        if motor.axis_error:
            self.emit(Errors.FAULT_BEFORE_MOTION.format(name=name))
            return
        if (
            name not in self.active_motor_names
            or motor.current_state != MotorState.CLOSED_LOOP_CONTROL
        ):
            self.active_motor_names.discard(name)
            self.emit(Errors.DISARMED.format(name=name))
            return
        current_degrees = None
        if command == "mr":
            if motor.current_position is None:
                self.emit(Errors.NO_RELATIVE_POSITION.format(name=name))
                return
            current_degrees = actuator_actions.get_current_position(name)
            if current_degrees is None:
                self.emit(Errors.NO_RELATIVE_POSITION.format(name=name))
                return
        target_degrees = position_target_degrees(
            command, angle_degrees, current_degrees
        )
        try:
            target_turns = actuator_actions.validate_target_position(
                name, target_degrees
            )
        except ValueError as error:
            self.emit(Errors.TARGET_REJECTED.format(name=name, error=error))
            return
        if actuator_actions.set_target_position(name, target_degrees):
            if command == "mr":
                self.emit(
                    f"Commanded {name} by {angle_degrees:g} "
                    f"degrees to {target_degrees:g} degrees "
                    f"({target_turns:.4f} motor turns)."
                )
            else:
                self.emit(
                    f"Commanded {name} to {target_degrees:g} "
                    f"degrees ({target_turns:.4f} motor turns)."
                )
        else:
            self.emit(Errors.TARGET_FAILED.format(name=name))

    def stop(self) -> None:
        """Request idle for every motor still tracked as active."""
        for name in self.active_motor_names:
            motor_actions.set_axis_state(name, MotorState.IDLE)


def run_motor_test(
    args: argparse.Namespace,
    read_command=input,
    emit=print,
    on_motors_configured=None,
    on_ready=None,
    should_stop=None,
) -> int:
    """Configure hardware, run a command session, and always clean up."""
    configured = False
    session = None
    can_actions.USE = True
    try:
        configure_device(os.fspath(args.config))
        configured = True
        motors = {
            name: motor_actions.get_state_snapshot(name)
            for name in motor_actions.get_names()
        }
        session = MotorTestSession(motors, emit, should_stop)
        if on_motors_configured is not None:
            on_motors_configured(motors)
        result = session.prepare(args.motor)
        if result is None:
            return 0
        if result:
            return result
        emit(COMMAND_HELP)
        if on_ready is not None:
            on_ready()
        session.run(read_command)
    except KeyboardInterrupt:
        emit("\nStopping motor test.")
    except (OSError, ValueError) as error:
        emit(Errors.START_FAILED.format(error=error))
        return 7
    finally:
        if session is not None:
            session.stop()
        if configured:
            for bus_name in can_actions.get_names():
                try:
                    can_actions.close(bus_name)
                except (OSError, ValueError):
                    pass
    return 0


class CommandInput(Input):
    """Single-line command input with current-session history."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_history: list[str] = []
        self.history_index = 0
        self.pending_value = ""

    def remember(self, command: str) -> None:
        """Record a submitted command while avoiding adjacent duplicates."""
        if command and (
            not self.command_history or self.command_history[-1] != command
        ):
            self.command_history.append(command)
            del self.command_history[:-100]
        self.history_index = len(self.command_history)
        self.pending_value = ""

    def on_key(self, event: events.Key) -> None:
        """Navigate command history with Up and Down."""
        if event.key not in HISTORY_KEYS or not self.command_history:
            return
        if event.key == "up":
            if self.history_index == len(self.command_history):
                self.pending_value = self.value
            self.history_index = max(0, self.history_index - 1)
            self.value = self.command_history[self.history_index]
        else:
            self.history_index = min(len(self.command_history), self.history_index + 1)
            self.value = (
                self.pending_value
                if self.history_index == len(self.command_history)
                else self.command_history[self.history_index]
            )
        self.cursor_position = len(self.value)
        event.prevent_default()
        event.stop()


class MotorTestApp(App[int]):
    """Textual front end for the safety-oriented ODrive command loop."""

    CSS = """
    Screen {
        background: #111318;
        color: #d7dae0;
    }

    #layout {
        height: 100%;
        padding: 1 2;
    }

    #log {
        height: 1fr;
        min-height: 8;
        border: none;
        background: #111318;
        padding: 0 1;
        scrollbar-color: #6f7787;
        scrollbar-background: #20232a;
    }

    #command {
        height: 3;
        margin-top: 1;
        border: none;
        background: #262626;
        padding: 0 1;
    }

    #command:focus {
        border: none;
        background: #333333;
    }

    #status-row {
        height: auto;
        min-height: 1;
        margin-top: 0;
    }

    #can-status {
        width: auto;
        min-width: 16;
        margin-right: 2;
    }

    #command-list {
        width: 1fr;
        color: #8f96a3;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("ctrl+q", "request_quit", "Stop"),
        ("ctrl+d", "request_quit", "Stop"),
    ]

    STOP = object()
    COMMAND_HINT = (
        "mp abs  mr rel  arm  disarm  read  speed  c/f calibrate  "
        "home  clear  q quit  select log + Ctrl/Cmd-C copy"
    )

    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.commands: queue.Queue[object] = queue.Queue()
        self.stop_event = threading.Event()
        self.session_thread: threading.Thread | None = None
        self.motors = None
        self.can_ready = False
        self.last_faults: tuple[tuple[str, int, tuple[int, ...]], ...] | None = None
        self.last_error_detail_requests: dict[str, float] = {}
        self.session_return_code = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="layout"):
            yield TextArea(
                id="log",
                soft_wrap=True,
                read_only=True,
                show_cursor=False,
                highlight_cursor_line=False,
                max_checkpoints=0,
            )
            yield CommandInput(
                placeholder="Enter a command, for example: mp 15 0",
                id="command",
                disabled=True,
            )
            with Horizontal(id="status-row"):
                yield Static(
                    Text("● CAN CHECKING", style="bold yellow"), id="can-status"
                )
                yield Static(self.COMMAND_HINT, id="command-list")

    def on_mount(self) -> None:
        self.set_interval(0.25, self.refresh_can_status)
        self.write_log(
            "Motor control starts disarmed. Keep the mechanism clear and an "
            "emergency stop available.",
            "bold yellow",
        )
        self.write_log(
            "Log text is selectable. Drag to highlight and press Ctrl-C/Cmd-C "
            "to copy over SSH; use Shift-drag for native terminal selection."
        )
        self.session_thread = threading.Thread(
            target=self._run_session,
            name="catbot-motor-test",
            daemon=True,
        )
        self.session_thread.start()

    def _call_from_session(self, callback, *args) -> None:
        try:
            self.call_from_thread(callback, *args)
        except RuntimeError:
            pass

    def _run_session(self) -> None:
        try:
            result = run_motor_test(
                self.args,
                read_command=self.read_command,
                emit=self.emit,
                on_motors_configured=lambda motors: self._call_from_session(
                    self.set_motors, motors
                ),
                on_ready=lambda: self._call_from_session(self.set_ready),
                should_stop=self.stop_event.is_set,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.emit(Errors.INTERFACE_FAILED.format(error=error))
            result = 7
        self._call_from_session(self.session_finished, result)

    def read_command(self, _prompt: str) -> str:
        """Wait for the Textual input to submit the next command."""
        self._call_from_session(self.set_input_ready, True)
        value = self.commands.get()
        self._call_from_session(self.set_input_ready, False)
        if value is self.STOP:
            raise EOFError
        return str(value)

    def emit(self, *values, sep=" ", end="\n") -> None:
        """Send command-loop output safely to the log widget."""
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        self._call_from_session(self.write_output, message.rstrip("\n"))

    def set_motors(self, motors) -> None:
        self.motors = motors

    def set_ready(self) -> None:
        self.can_ready = True
        self.refresh_can_status()

    def set_input_ready(self, ready: bool) -> None:
        command = self.query_one("#command", CommandInput)
        command.disabled = not ready
        if ready:
            command.focus()

    def session_finished(self, result: int) -> None:
        self.session_return_code = result
        self.exit(result=result)

    @on(Input.Submitted, "#command")
    def submit_command(self, event: Input.Submitted) -> None:
        command = self.query_one("#command", CommandInput)
        if command.disabled:
            return
        value = event.value.strip()
        command.remember(value)
        command.value = ""
        command.disabled = True
        self.write_log(Text.assemble(("> ", "bold cyan"), value))
        self.commands.put(value)

    def action_request_quit(self) -> None:
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.query_one("#command", CommandInput).disabled = True
        self.query_one("#can-status", Static).update(
            Text("● STOPPING", style="bold yellow")
        )
        self.commands.put(self.STOP)

    def write_log(self, message, style: str | None = None) -> None:
        del style  # TextArea provides selection and SSH clipboard support, not markup.
        log = self.query_one("#log", TextArea)
        line = str(message)
        if log.text:
            line = f"\n{line}"
        log.insert(line, log.document.end, maintain_selection_offset=True)
        if log.document.line_count > 2000:
            excess_lines = log.document.line_count - 2000
            log.delete((0, 0), (excess_lines, 0), maintain_selection_offset=True)
        log.scroll_end(animate=False)

    def write_output(self, message: str) -> None:
        lower = message.lower()
        if "error(s) detected" in lower or lower.startswith("  "):
            style = "red"
        elif any(marker in lower for marker in ERROR_LOG_MARKERS):
            style = "bold red"
        elif "warning" in lower or "disarmed" in lower:
            style = "yellow"
        elif any(marker in lower for marker in SUCCESS_LOG_MARKERS):
            style = "green"
        else:
            style = None
        self.write_log(message, style)

    def refresh_can_status(self) -> None:
        status = self.query_one("#can-status", Static)
        if self.stop_event.is_set():
            return
        if self.motors is None or not self.can_ready:
            status.update(Text("● CAN CHECKING", style="bold yellow"))
            return

        self.motors = {
            name: motor_actions.get_state_snapshot(name) for name in self.motors
        }
        now = time.monotonic()
        for name, motor in self.motors.items():
            if any(motor_fault_values(motor)) and (
                now - self.last_error_detail_requests.get(name, -math.inf) >= 1.0
            ):
                motor_actions.request_error_details(name)
                self.last_error_detail_requests[name] = now
        faults = tuple(
            (name, motor.axisID, motor_fault_values(motor))
            for name, motor in sorted(self.motors.items())
            if any(motor_fault_values(motor))
        )
        if faults:
            status.update(
                Text(
                    f"● CAN ERRORS ({len(faults)})",
                    style="bold red",
                )
            )
        else:
            status.update(Text("● CAN OK", style="bold green"))

        if self.last_faults is None:
            self.last_faults = ()
        if faults == self.last_faults:
            return
        if faults:
            self.write_log(
                f"CAN error status changed: {len(faults)} faulted axis"
                f"{'es' if len(faults) != 1 else ''}.",
                "bold red",
            )
            for name, axis_id, values in faults:
                self.write_log(
                    f"  {name} (axis {axis_id}): {describe_motor_fault(values)}",
                    "red",
                )
        elif self.last_faults:
            self.write_log("CAN errors cleared.", "bold green")
        self.last_faults = faults

    def on_unmount(self) -> None:
        self.stop_event.set()
        self.commands.put(self.STOP)


def main() -> int:
    """Parse arguments and launch the Textual motor-test interface."""
    app = MotorTestApp(parse_args())
    result = app.run()
    if app.session_thread is not None:
        app.session_thread.join(timeout=HEARTBEAT_TIMEOUT_SECONDS + 1)
    return app.session_return_code if result is None else result


if __name__ == "__main__":
    raise SystemExit(main())
