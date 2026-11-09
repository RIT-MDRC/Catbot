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

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

HEARTBEAT_TIMEOUT_SECONDS = 3.0


def parse_speed_degrees_per_second(value: str) -> float:
    """Parse a finite, positive joint-speed limit."""
    speed = float(value)
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("speed must be finite and greater than zero")
    return speed


def parse_angle_degrees(value: str) -> float:
    """Parse a finite joint-angle command."""
    angle_degrees = float(value)
    if not math.isfinite(angle_degrees):
        raise ValueError("angle must be finite")
    return angle_degrees


def position_target_degrees(
    command: str, angle_degrees: float, current_degrees: float | None = None
) -> float:
    """Resolve an absolute or relative command to an absolute logical target."""
    if command == "mp":
        return angle_degrees
    if command == "mr":
        if current_degrees is None:
            raise ValueError("relative motion requires a current position")
        return current_degrees + angle_degrees
    raise ValueError(f'unknown position command "{command}"')


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments before importing hardware modules."""
    default_config = Path(__file__).with_name("demo_config.json")
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
        default=default_config,
        help=f"device configuration file (default: {default_config})",
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
    names = {
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
    known_mask = 0
    decoded = []
    for flag, name in names.items():
        known_mask |= flag
        if error & flag:
            decoded.append(name)
    unknown_bits = error & ~known_mask
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
    emit("ODrive error(s) detected on the CAN bus:")
    for error in errors:
        emit(f"  {error}")
    return True


def wait_for(motor_name, predicate, timeout: float, should_stop=None) -> bool:
    """Wait for asynchronous CAN feedback to satisfy a predicate."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if should_stop is not None and should_stop():
            return False
        from component.motor import motor_actions

        if predicate(motor_actions.get_state_snapshot(motor_name)):
            return True
        time.sleep(0.05)
    return False


def run_motor_test(
    args: argparse.Namespace,
    read_command=input,
    emit=print,
    on_motors_configured=None,
    on_ready=None,
    should_stop=None,
) -> int:
    """Configure ODrives and run the command loop through injectable I/O."""
    print = emit
    foundation_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, os.fspath(foundation_root))

    from component.actuator import actuator_actions
    from component.can import can_actions
    from component.motor import motor_actions
    from component.motor.odrive_enums import MotorState
    from state_management import configure_device

    configured = False
    selected_motors = []
    active_motor_names = set()
    can_actions.USE = True
    try:
        configure_device(os.fspath(args.config))
        configured = True
        motor_names = motor_actions.get_names()
        motors = {
            name: motor_actions.get_state_snapshot(name) for name in motor_names
        }
        if on_motors_configured is not None:
            on_motors_configured(motors)
        default_motor_name = None
        if args.motor:
            matches = find_motors(motors, args.motor)
            if not matches or (
                len(matches) != 1 and not is_multi_motor_selector(args.motor)
            ):
                if matches and not is_multi_motor_selector(args.motor):
                    names = ", ".join(name for name, _ in matches)
                    print(f'Axis ID "{args.motor}" is ambiguous: {names}.')
                else:
                    print(f'Unknown motor name or axis ID "{args.motor}".')
                print(f"Configured motors: {describe_motors(motors)}")
                return 2
            selected_motors = matches
            default_motor_name = args.motor
            if len(matches) == 1:
                default_motor_name = matches[0][0]
        else:
            print(
                "No default motor selected; include a motor name or axis ID "
                "in commands."
            )
            print(f"Configured motors: {describe_motors(motors)}")

        for selected_motor_name, _ in selected_motors:
            if should_stop is not None and should_stop():
                return 0
            print(f"Waiting for an ODrive heartbeat from {selected_motor_name}...")
            if not wait_for(
                selected_motor_name,
                lambda motor: motor.current_state != MotorState.UNDEFINED,
                HEARTBEAT_TIMEOUT_SECONDS,
                should_stop,
            ):
                if should_stop is not None and should_stop():
                    return 0
                print(f"No heartbeat received from {selected_motor_name}.")
                print(
                    "Confirm can0 is up, the 250000 bitrate matches the ODrive, "
                    "and the configured axis ID is correct."
                )
                return 3
        if selected_motors:
            report_bus_errors(motors, emit)
            selected_names = ", ".join(name for name, _ in selected_motors)
            print(f"{selected_names} disarmed; type 'arm' to enable the selection.")

        print(
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
        if on_ready is not None:
            on_ready()
        while True:
            motors = {
                name: motor_actions.get_state_snapshot(name) for name in motor_names
            }
            try:
                raw_value = read_command("angle> ").strip()
            except EOFError:
                break
            parts = raw_value.split(maxsplit=1)
            command = parts[0].lower() if parts else ""
            command_matches = []
            if not parts:
                print(
                    "Invalid command. Use mp or mr with a finite angle, "
                    "a shortcut command, or q."
                )
                continue
            if command in {"q", "quit", "exit"}:
                break
            if command == "speed":
                speed_parts = parts[1].split(maxsplit=1) if len(parts) == 2 else []
                try:
                    speed_degrees = parse_speed_degrees_per_second(speed_parts[0])
                except (IndexError, ValueError):
                    print(
                        "Invalid speed. Use: speed <positive degrees/second> "
                        "[motor[,motor...]]."
                    )
                    continue
                selector = (
                    speed_parts[1] if len(speed_parts) == 2 else default_motor_name
                )
                speed_matches = find_motors(motors, selector)
                if not speed_matches or (
                    len(speed_matches) != 1 and not is_multi_motor_selector(selector)
                ):
                    print(
                        "Invalid command: supply valid motor names or axis IDs "
                        "(comma-separated for multiple motors), or start "
                        "motor-test with --motor."
                    )
                    print(f"Configured motors: {describe_motors(motors)}")
                    continue
                for speed_motor_name, _ in speed_matches:
                    if actuator_actions.set_trajectory_speed(
                        speed_motor_name, speed_degrees
                    ):
                        speed_turns = (
                            actuator_actions.get_trajectory_velocity_motor_turns(
                                speed_motor_name
                            )
                        )
                        print(
                            f"Set {speed_motor_name} trajectory speed to "
                            f"{speed_degrees:g} degrees/second "
                            f"({speed_turns:.4f} motor turns/second)."
                        )
                    else:
                        print(f"Failed to set speed for {speed_motor_name}.")
                continue
            shortcut_states = {
                "c": ("motor calibration", MotorState.MOTOR_CALIBRATION),
                "calibrate": ("motor calibration", MotorState.MOTOR_CALIBRATION),
                "f": ("full calibration", MotorState.FULL_CALIBRATION_SEQUENCE),
                "full": ("full calibration", MotorState.FULL_CALIBRATION_SEQUENCE),
                "full-calibration": (
                    "full calibration",
                    MotorState.FULL_CALIBRATION_SEQUENCE,
                ),
                "h": ("homing", MotorState.HOMING),
                "home": ("homing", MotorState.HOMING),
            }
            if (
                command
                in {
                    "arm",
                    "a",
                    "disarm",
                    "d",
                    "r",
                    "read",
                    "rs",
                    "read-speed",
                    "e",
                    "clear",
                }
                or command in shortcut_states
            ):
                selector = parts[1] if len(parts) == 2 else default_motor_name
                command_matches = find_motors(motors, selector)
                if not command_matches or (
                    len(command_matches) != 1 and not is_multi_motor_selector(selector)
                ):
                    print(
                        "Invalid command: supply valid motor names or axis IDs "
                        "(comma-separated for multiple motors), or start "
                        "motor-test with --motor."
                    )
                    print(f"Configured motors: {describe_motors(motors)}")
                    continue
            if command in {"r", "read"}:
                for command_motor_name, command_motor in command_matches:
                    if command_motor.current_position is None:
                        print(
                            f"No encoder position received from {command_motor_name}."
                        )
                        continue
                    angle_degrees = actuator_actions.get_current_position(
                        command_motor_name
                    )
                    print(
                        f"{command_motor_name}: {angle_degrees:.2f} degrees "
                        f"({command_motor.current_position:.4f} motor turns)."
                    )
                continue
            if command in {"rs", "read-speed"}:
                for command_motor_name, command_motor in command_matches:
                    if command_motor.current_velocity is None:
                        print(f"No encoder speed received from {command_motor_name}.")
                        continue
                    speed_degrees = actuator_actions.get_current_velocity(
                        command_motor_name
                    )
                    print(
                        f"{command_motor_name}: {speed_degrees:.2f} degrees/second "
                        f"({command_motor.current_velocity:.4f} motor turns/second)."
                    )
                continue
            if command in {"arm", "a"}:
                for command_motor_name, command_motor in command_matches:
                    if command_motor.axis_error:
                        print(
                            f"Clear the ODrive error on {command_motor_name} before arming."
                        )
                        continue
                    if command_motor.current_position is None:
                        print(
                            f"No encoder position received from {command_motor_name}; "
                            "refusing to arm without a safe initial hold position."
                        )
                        continue
                    print(
                        f"WARNING: arming {command_motor_name} enables motor torque; "
                        "keep the mechanism clear."
                    )
                    setup_commands_sent = actuator_actions.configure_trajectory(
                        command_motor_name
                    ) and motor_actions.set_target_position(
                        command_motor_name,
                        command_motor.current_position,
                    )
                    if not setup_commands_sent or not motor_actions.set_axis_state(
                        command_motor_name,
                        MotorState.CLOSED_LOOP_CONTROL,
                    ):
                        print(
                            f"Failed to send the arm command sequence to {command_motor_name}."
                        )
                        continue
                    if not wait_for(
                        command_motor_name,
                        lambda motor: (
                            motor.current_state == MotorState.CLOSED_LOOP_CONTROL
                        ),
                        HEARTBEAT_TIMEOUT_SECONDS,
                        should_stop,
                    ):
                        print(f"{command_motor_name} did not confirm that it is armed.")
                        motor_actions.set_axis_state(command_motor_name, MotorState.IDLE)
                        continue
                    active_motor_names.add(command_motor_name)
                    print(f"Armed {command_motor_name} in position control.")
                report_bus_errors(motors, emit)
                continue
            if command in {"disarm", "d"}:
                for command_motor_name, command_motor in command_matches:
                    if not motor_actions.set_axis_state(
                        command_motor_name, MotorState.IDLE
                    ):
                        print(
                            f"Failed to send the disarm command to {command_motor_name}."
                        )
                        continue
                    if not wait_for(
                        command_motor_name,
                        lambda motor: motor.current_state == MotorState.IDLE,
                        HEARTBEAT_TIMEOUT_SECONDS,
                        should_stop,
                    ):
                        print(
                            f"{command_motor_name} did not confirm that it is disarmed."
                        )
                        continue
                    active_motor_names.discard(command_motor_name)
                    print(f"Disarmed {command_motor_name}.")
                continue
            if command in {"e", "clear"}:
                for command_motor_name, _ in command_matches:
                    if motor_actions.clear_error_message(command_motor_name):
                        print(f"Requested error clear for {command_motor_name}.")
                    else:
                        print(f"Failed to clear errors for {command_motor_name}.")
                time.sleep(0.2)
                report_bus_errors(motors, emit)
                continue
            if command in shortcut_states:
                action_name, requested_state = shortcut_states[command]
                print(
                    f"WARNING: {action_name} moves the motor; keep the mechanism clear."
                )
                for command_motor_name, _ in command_matches:
                    if motor_actions.set_axis_state(
                        command_motor_name, requested_state
                    ):
                        print(f"Requested {action_name} for {command_motor_name}.")
                    else:
                        print(f"Failed to send {action_name} to {command_motor_name}.")
                continue
            if command not in {"mp", "mr"}:
                print(
                    "Invalid command. Use mp <angle> [motor] for an absolute "
                    "position or mr <angle> [motor] for relative motion."
                )
                continue
            angle_parts = parts[1].split(maxsplit=1) if len(parts) == 2 else []
            try:
                angle_degrees = parse_angle_degrees(angle_parts[0])
            except (IndexError, ValueError):
                print(
                    f"Invalid command. Use {command} <finite angle> "
                    "[motor[,motor...]]."
                )
                continue
            angle_selector = (
                angle_parts[1] if len(angle_parts) == 2 else default_motor_name
            )
            angle_matches = find_motors(motors, angle_selector)
            if not angle_matches or (
                len(angle_matches) != 1 and not is_multi_motor_selector(angle_selector)
            ):
                print(
                    "Invalid command: supply valid motor names or axis IDs after "
                    f"'{command} <angle>' (comma-separated for multiple motors), or start "
                    "motor-test with --motor."
                )
                print(f"Configured motors: {describe_motors(motors)}")
                continue
            report_bus_errors(motors, emit)
            for angle_motor_name, angle_motor in angle_matches:
                if angle_motor.axis_error:
                    print(
                        f"Clear the error on {angle_motor_name} before commanding motion."
                    )
                    continue
                if (
                    angle_motor_name not in active_motor_names
                    or angle_motor.current_state != MotorState.CLOSED_LOOP_CONTROL
                ):
                    active_motor_names.discard(angle_motor_name)
                    print(
                        f"{angle_motor_name} is disarmed; run 'arm {angle_motor_name}'."
                    )
                    continue
                current_degrees = None
                if command == "mr":
                    if angle_motor.current_position is None:
                        print(
                            f"No encoder position received from {angle_motor_name}; "
                            "relative motion requires a current position."
                        )
                        continue
                    current_degrees = actuator_actions.get_current_position(
                        angle_motor_name
                    )
                    if current_degrees is None:
                        print(
                            f"No encoder position received from {angle_motor_name}; "
                            "relative motion requires a current position."
                        )
                        continue
                target_degrees = position_target_degrees(
                    command, angle_degrees, current_degrees
                )
                try:
                    target_turns = actuator_actions.validate_target_position(
                        angle_motor_name, target_degrees
                    )
                except ValueError as error:
                    print(f"Command rejected for {angle_motor_name}: {error}.")
                    continue
                if actuator_actions.set_target_position(
                    angle_motor_name, target_degrees
                ):
                    if command == "mr":
                        print(
                            f"Commanded {angle_motor_name} by {angle_degrees:g} "
                            f"degrees to {target_degrees:g} degrees "
                            f"({target_turns:.4f} motor turns)."
                        )
                    else:
                        print(
                            f"Commanded {angle_motor_name} to {target_degrees:g} "
                            f"degrees ({target_turns:.4f} motor turns)."
                        )
                else:
                    print(
                        f"Command rejected for {angle_motor_name}; check its position bounds."
                    )
    except KeyboardInterrupt:
        print("\nStopping motor test.")
    except (OSError, ValueError) as error:
        print(f"Unable to start motor test: {error}")
        return 7
    finally:
        for motor_name in active_motor_names:
            motor_actions.set_axis_state(motor_name, MotorState.IDLE)
        if configured and can_actions is not None:
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
        if event.key not in {"up", "down"} or not self.command_history:
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
        border: round #464b57;
        background: #111318;
        padding: 0 1;
        scrollbar-color: #6f7787;
        scrollbar-background: #20232a;
    }

    #command {
        height: 3;
        margin-top: 1;
        border: round #6f7787;
        background: #181b21;
    }

    #command:focus {
        border: round #8ab4f8;
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
        ("ctrl+c", "request_quit", "Stop"),
        ("ctrl+d", "request_quit", "Stop"),
    ]

    STOP = object()
    COMMAND_HINT = (
        "mp abs  mr rel  arm  disarm  read  speed  c/f calibrate  "
        "home  clear  q quit"
    )

    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.commands: queue.Queue[object] = queue.Queue()
        self.stop_event = threading.Event()
        self.session_thread: threading.Thread | None = None
        self.motors = None
        self.can_ready = False
        self.last_faults: tuple[tuple[str, int, int], ...] | None = None
        self.session_return_code = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="layout"):
            yield RichLog(
                id="log",
                wrap=True,
                highlight=False,
                markup=False,
                max_lines=2000,
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
        log = self.query_one("#log", RichLog)
        log.border_title = " Catbot motor test "
        command = self.query_one("#command", CommandInput)
        command.border_title = " Command "
        self.set_interval(0.25, self.refresh_can_status)
        self.write_log(
            "Motor control starts disarmed. Keep the mechanism clear and an "
            "emergency stop available.",
            "bold yellow",
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
            self.emit(f"Motor-test interface failed: {error}")
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
        """Send command-loop output safely to the RichLog widget."""
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
        content = Text(str(message), style=style) if style else message
        self.query_one("#log", RichLog).write(content)

    def write_output(self, message: str) -> None:
        lower = message.lower()
        if "error(s) detected" in lower or lower.startswith("  "):
            style = "red"
        elif any(
            marker in lower
            for marker in (
                "invalid command",
                "failed",
                "unable",
                "command rejected",
                "clear the error",
                "no heartbeat",
            )
        ):
            style = "bold red"
        elif "warning" in lower or "disarmed" in lower:
            style = "yellow"
        elif any(marker in lower for marker in ("armed ", "commanded ", "set ")):
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
        faults = tuple(
            (name, motor.axisID, motor.axis_error)
            for name, motor in sorted(self.motors.items())
            if motor.axis_error
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
            for name, axis_id, error in faults:
                self.write_log(
                    f"  {name} (axis {axis_id}): 0x{error:x} "
                    f"{describe_axis_error(error)}",
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
