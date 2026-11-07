"""Interactively command configured ODrive motors by joint angle."""

import argparse
import math
import os
import readline
import sys
import time
from pathlib import Path

MOTOR_TURNS_PER_ACTUATOR_TURN = 64.0
MIN_ANGLE_DEGREES = -41.0
MAX_ANGLE_DEGREES = 41.0
HEARTBEAT_TIMEOUT_SECONDS = 3.0
TRAJECTORY_VELOCITY_TURNS_PER_SECOND = 1.0
TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED = 1.0

readline.set_history_length(100)


def degrees_to_motor_turns(degrees: float) -> float:
    """Convert homed joint degrees to ODrive motor turns."""
    return degrees * MOTOR_TURNS_PER_ACTUATOR_TURN / 360.0


def motor_turns_to_degrees(turns: float) -> float:
    """Convert ODrive motor turns to homed joint degrees."""
    return turns * 360.0 / MOTOR_TURNS_PER_ACTUATOR_TURN


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
    if not MIN_ANGLE_DEGREES <= angle_degrees <= MAX_ANGLE_DEGREES:
        raise ValueError(
            f"angle must be between {MIN_ANGLE_DEGREES:g} and "
            f"{MAX_ANGLE_DEGREES:g} degrees"
        )
    return angle_degrees


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


def report_bus_errors(motors) -> bool:
    """Print every currently reported ODrive error on the configured CAN bus."""
    errors = [
        f"{name} (axis {motor.axisID}): 0x{motor.axis_error:x} "
        f"({describe_axis_error(motor.axis_error)})"
        for name, motor in sorted(motors.items())
        if motor.axis_error
    ]
    if not errors:
        return False
    print("ODrive error(s) detected on the CAN bus:")
    for error in errors:
        print(f"  {error}")
    return True


def wait_for(motor, predicate, timeout: float) -> bool:
    """Wait for asynchronous CAN feedback to satisfy a predicate."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(motor):
            return True
        time.sleep(0.05)
    return False


def main() -> int:
    """Configure ODrives and run the interactive angle prompt."""
    args = parse_args()
    foundation_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, os.fspath(foundation_root))

    from component.can import can_actions
    from component.motor import motor_actions
    from component.motor.odrive_enums import ControlMode, InputMode, MotorState
    from state_management import configure_device

    configured = False
    selected_motors = []
    active_motor_names = set()
    trajectory_velocities = {}
    can_actions = None
    try:
        configure_device(os.fspath(args.config))
        configured = True
        motors = motor_actions.ctx.store
        trajectory_velocities = {
            name: TRAJECTORY_VELOCITY_TURNS_PER_SECOND for name in motors
        }
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

        for selected_motor_name, selected_motor in selected_motors:
            print(f"Waiting for an ODrive heartbeat from {selected_motor_name}...")
            if not wait_for(
                selected_motor,
                lambda motor: motor.current_state != MotorState.UNDEFINED,
                HEARTBEAT_TIMEOUT_SECONDS,
            ):
                print(f"No heartbeat received from {selected_motor_name}.")
                print(
                    "Confirm can0 is up, the 250000 bitrate matches the ODrive, "
                    "and the configured axis ID is correct."
                )
                return 3
        if selected_motors:
            report_bus_errors(motors)
            selected_names = ", ".join(name for name, _ in selected_motors)
            print(f"{selected_names} disarmed; type 'arm' to enable the selection.")

        print(
            "Commands: arm [motor[,motor...]], disarm [motor[,motor...]], "
            "r/read [motor[,motor...]] = read angle, "
            "speed <deg/s> [motor[,motor...]], "
            "rs/read-speed [motor[,motor...]], "
            "angle [motor[,motor...]], "
            "c [motor] = motor calibration, "
            "f [motor] = full calibration, h [motor] = home, "
            "e [motor] = clear errors, q = stop."
        )
        while True:
            try:
                raw_value = input("angle> ").strip()
            except EOFError:
                break
            parts = raw_value.split(maxsplit=1)
            command = parts[0].lower() if parts else ""
            if not parts:
                print(
                    "Invalid command. Enter an angle from -41 to 41 degrees, "
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
                speed_turns = degrees_to_motor_turns(speed_degrees)
                for speed_motor_name, _ in speed_matches:
                    if motor_actions.set_trajectory_velocity(
                        speed_motor_name, speed_turns
                    ):
                        trajectory_velocities[speed_motor_name] = speed_turns
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
                    angle_degrees = motor_turns_to_degrees(
                        command_motor.current_position
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
                    speed_degrees = motor_turns_to_degrees(
                        command_motor.current_velocity
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
                    setup_commands_sent = (
                        motor_actions.set_controller_mode(
                            command_motor_name,
                            ControlMode.POSITION_CONTROL,
                            InputMode.TRAP_TRAJ,
                        )
                        and motor_actions.set_trajectory_velocity(
                            command_motor_name,
                            trajectory_velocities[command_motor_name],
                        )
                        and motor_actions.set_trajectory_accel(
                            command_motor_name,
                            TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED,
                        )
                        and motor_actions.set_target_position(
                            command_motor_name, command_motor.current_position
                        )
                    )
                    if not setup_commands_sent or not motor_actions.set_axis_state(
                        command_motor_name, MotorState.CLOSED_LOOP_CONTROL
                    ):
                        print(
                            f"Failed to send the arm command sequence to {command_motor_name}."
                        )
                        continue
                    if not wait_for(
                        command_motor,
                        lambda motor: motor.current_state
                        == MotorState.CLOSED_LOOP_CONTROL,
                        HEARTBEAT_TIMEOUT_SECONDS,
                    ):
                        print(f"{command_motor_name} did not confirm that it is armed.")
                        motor_actions.set_axis_state(
                            command_motor_name, MotorState.IDLE
                        )
                        continue
                    active_motor_names.add(command_motor_name)
                    print(f"Armed {command_motor_name} in position control.")
                report_bus_errors(motors)
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
                        command_motor,
                        lambda motor: motor.current_state == MotorState.IDLE,
                        HEARTBEAT_TIMEOUT_SECONDS,
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
                report_bus_errors(motors)
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
            try:
                angle_degrees = parse_angle_degrees(parts[0])
            except ValueError:
                print(
                    "Invalid command. Enter an angle from -41 to 41 degrees, "
                    "a shortcut command, or q."
                )
                continue
            angle_selector = parts[1] if len(parts) == 2 else default_motor_name
            angle_matches = find_motors(motors, angle_selector)
            if not angle_matches or (
                len(angle_matches) != 1 and not is_multi_motor_selector(angle_selector)
            ):
                print(
                    "Invalid command: supply valid motor names or axis IDs after "
                    "the angle (comma-separated for multiple motors), or start "
                    "motor-test with --motor."
                )
                print(f"Configured motors: {describe_motors(motors)}")
                continue
            report_bus_errors(motors)
            target_turns = degrees_to_motor_turns(angle_degrees)
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
                if motor_actions.set_target_position(angle_motor_name, target_turns):
                    print(
                        f"Commanded {angle_motor_name} to {angle_degrees:g} degrees ({target_turns:.4f} motor turns)."
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
            for bus_name in list(can_actions.ctx.store):
                try:
                    can_actions.close(bus_name)
                except (OSError, ValueError):
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
