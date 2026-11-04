"""Interactively command one configured ODrive motor by joint angle."""

import argparse
import os
import readline
import sys
import time
from pathlib import Path

MOTOR_TURNS_PER_30_DEGREES = 5.33
HEARTBEAT_TIMEOUT_SECONDS = 3.0
TRAJECTORY_VELOCITY_TURNS_PER_SECOND = 1.0
TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED = 1.0

readline.set_history_length(100)


def degrees_to_motor_turns(degrees: float) -> float:
    """Convert homed joint degrees to ODrive motor turns."""
    return degrees * MOTOR_TURNS_PER_30_DEGREES / 30.0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments before importing hardware modules."""
    default_config = Path(__file__).with_name("demo_config.json")
    parser = argparse.ArgumentParser(
        description="Move one homed ODrive motor to typed joint angles."
    )
    parser.add_argument(
        "--motor",
        help="configured motor name or CAN axis ID, for example odrive_1 or 0",
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
    return ", ".join(
        f"{name} (axis {motor.axisID})" for name, motor in sorted(motors.items())
    ) or "none"


def find_motors(motors, selector: str | None):
    """Find a motor by exact configured name or decimal CAN axis ID."""
    if selector is None:
        return []
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


def report_bus_errors(motors) -> bool:
    """Print every currently reported ODrive error on the configured CAN bus."""
    errors = [
        f"{name} (axis {motor.axisID}): 0x{motor.axis_error:x}"
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
    """Configure one ODrive and run the interactive angle prompt."""
    args = parse_args()
    foundation_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, os.fspath(foundation_root))

    from component.can import can_actions
    from component.motor import motor_actions
    from component.motor.odrive_enums import ControlMode, InputMode, MotorState
    from state_management import configure_device

    configured = False
    selected_motor = None
    active_motor_names = set()
    can_actions = None
    try:
        configure_device(os.fspath(args.config))
        configured = True
        motors = motor_actions.ctx.store
        default_motor_name = None
        if args.motor:
            matches = find_motors(motors, args.motor)
            if len(matches) != 1:
                if matches:
                    names = ", ".join(name for name, _ in matches)
                    print(f'Axis ID "{args.motor}" is ambiguous: {names}.')
                else:
                    print(f'Unknown motor name or axis ID "{args.motor}".')
                print(f"Configured motors: {describe_motors(motors)}")
                return 2
            default_motor_name, selected_motor = matches[0]
            args.motor = default_motor_name
        else:
            print(
                "No default motor selected; include a motor name or axis ID "
                "in commands."
            )
            print(f"Configured motors: {describe_motors(motors)}")

        if selected_motor is not None:
            print(f"Waiting for an ODrive heartbeat from {default_motor_name}...")
            if not wait_for(
                selected_motor,
                lambda motor: motor.current_state != MotorState.UNDEFINED,
                HEARTBEAT_TIMEOUT_SECONDS,
            ):
                print(
                    "No heartbeat received. Confirm can0 is up, the 250000 bitrate "
                    "matches the ODrive, and the configured axis ID is correct."
                )
                return 3
            report_bus_errors(motors)

            if not motor_actions.set_controller_mode(
                default_motor_name,
                ControlMode.POSITION_CONTROL,
                InputMode.TRAP_TRAJ,
            ):
                print("Failed to send position-control mode.")
                return 5
            if not motor_actions.set_trajectory_velocity(
                default_motor_name, TRAJECTORY_VELOCITY_TURNS_PER_SECOND
            ):
                print("Failed to set trajectory velocity.")
                return 5
            if not motor_actions.set_trajectory_accel(
                default_motor_name, TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED
            ):
                print("Failed to set trajectory acceleration.")
                return 5
            if not selected_motor.axis_error:
                motor_actions.set_axis_state(
                    default_motor_name, MotorState.CLOSED_LOOP_CONTROL
                )
                if not wait_for(
                    selected_motor,
                    lambda motor: motor.current_state
                    == MotorState.CLOSED_LOOP_CONTROL,
                    HEARTBEAT_TIMEOUT_SECONDS,
                ):
                    print(
                        "The ODrive did not enter closed-loop control. "
                        "Not moving motor."
                    )
                    report_bus_errors(motors)
                else:
                    active_motor_names.add(default_motor_name)

        print(
            "Commands: angle [motor], c [motor] = motor calibration, "
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
            if command in {"q", "quit", "exit"}:
                break
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
            if command in {"e", "clear"} or command in shortcut_states:
                selector = parts[1] if len(parts) == 2 else default_motor_name
                command_matches = find_motors(motors, selector)
                if len(command_matches) != 1:
                    print(
                        "Invalid command: supply one valid motor name or axis ID, "
                        "or start motor-test with --motor."
                    )
                    print(f"Configured motors: {describe_motors(motors)}")
                    continue
                command_motor_name, _ = command_matches[0]
            if command in {"e", "clear"}:
                if motor_actions.clear_error_message(command_motor_name):
                    print(f"Requested error clear for {command_motor_name}.")
                    time.sleep(0.2)
                    report_bus_errors(motors)
                else:
                    print("Failed to send the clear-errors command.")
                continue
            if command in shortcut_states:
                action_name, requested_state = shortcut_states[command]
                print(
                    f"WARNING: {action_name} moves the motor; keep the mechanism clear."
                )
                if motor_actions.set_axis_state(
                    command_motor_name, requested_state
                ):
                    print(f"Requested {action_name} for {command_motor_name}.")
                else:
                    print(f"Failed to send the {action_name} command.")
                continue
            try:
                angle_degrees = float(parts[0])
            except ValueError:
                print("Invalid command. Enter an angle, a shortcut command, or q.")
                continue
            angle_selector = parts[1] if len(parts) == 2 else default_motor_name
            angle_matches = find_motors(motors, angle_selector)
            if len(angle_matches) != 1:
                print(
                    "Invalid command: supply one valid motor name or axis ID after "
                    "the angle, or start motor-test with --motor."
                )
                print(f"Configured motors: {describe_motors(motors)}")
                continue
            angle_motor_name, angle_motor = angle_matches[0]
            report_bus_errors(motors)
            if angle_motor.axis_error:
                print("Clear the error before commanding motion.")
                continue
            if not motor_actions.set_controller_mode(
                angle_motor_name,
                ControlMode.POSITION_CONTROL,
                InputMode.TRAP_TRAJ,
            ):
                print("Failed to send position-control mode.")
                continue
            if not motor_actions.set_trajectory_velocity(
                angle_motor_name, TRAJECTORY_VELOCITY_TURNS_PER_SECOND
            ):
                print("Failed to set trajectory velocity.")
                continue
            if not motor_actions.set_trajectory_accel(
                angle_motor_name, TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED
            ):
                print("Failed to set trajectory acceleration.")
                continue
            if angle_motor.current_state != MotorState.CLOSED_LOOP_CONTROL:
                motor_actions.set_axis_state(
                    angle_motor_name, MotorState.CLOSED_LOOP_CONTROL
                )
                if not wait_for(
                    angle_motor,
                    lambda motor: motor.current_state
                    == MotorState.CLOSED_LOOP_CONTROL,
                    HEARTBEAT_TIMEOUT_SECONDS,
                ):
                    print("The ODrive is not in closed-loop control. Not moving motor.")
                    report_bus_errors(motors)
                    continue
            active_motor_names.add(angle_motor_name)
            target_turns = degrees_to_motor_turns(angle_degrees)
            if motor_actions.set_target_position(angle_motor_name, target_turns):
                print(
                    f"Commanded {angle_motor_name} to {angle_degrees:g} degrees "
                    f"({target_turns:.4f} motor turns)."
                )
            else:
                print("Command rejected; check the configured position bounds.")
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
