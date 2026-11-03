"""Interactively command one configured ODrive motor by joint angle."""

import argparse
import os
import sys
import time
from pathlib import Path

MOTOR_TURNS_PER_30_DEGREES = 5.33
HEARTBEAT_TIMEOUT_SECONDS = 3.0
TRAJECTORY_VELOCITY_TURNS_PER_SECOND = 1.0
TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED = 1.0


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
        required=True,
        help="configured motor name, for example odrive_1",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help=f"device configuration file (default: {default_config})",
    )
    return parser.parse_args()


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
    can_actions = None
    try:
        configure_device(os.fspath(args.config))
        configured = True
        selected_motor = motor_actions.ctx.store.get(args.motor)
        if selected_motor is None:
            choices = ", ".join(sorted(motor_actions.ctx.store)) or "none"
            print(f'Unknown motor "{args.motor}". Configured motors: {choices}')
            return 2

        print(f"Waiting for an ODrive heartbeat from {args.motor}...")
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
        if selected_motor.axis_error:
            print(
                f"ODrive axis error: 0x{selected_motor.axis_error:x}. Not moving motor."
            )
            return 4

        if not motor_actions.set_controller_mode(
            args.motor,
            ControlMode.POSITION_CONTROL,
            InputMode.TRAP_TRAJ,
        ):
            print("Failed to send position-control mode.")
            return 5
        if not motor_actions.set_trajectory_velocity(
            args.motor, TRAJECTORY_VELOCITY_TURNS_PER_SECOND
        ):
            print("Failed to set trajectory velocity.")
            return 5
        if not motor_actions.set_trajectory_accel(
            args.motor, TRAJECTORY_ACCEL_TURNS_PER_SECOND_SQUARED
        ):
            print("Failed to set trajectory acceleration.")
            return 5
        if not motor_actions.set_axis_state(args.motor, MotorState.CLOSED_LOOP_CONTROL):
            print("Failed to request closed-loop control.")
            return 5
        if not wait_for(
            selected_motor,
            lambda motor: motor.current_state == MotorState.CLOSED_LOOP_CONTROL,
            HEARTBEAT_TIMEOUT_SECONDS,
        ):
            print("The ODrive did not enter closed-loop control. Not moving motor.")
            return 6

        print("Ready. Enter an absolute homed joint angle in degrees, or q to stop.")
        while True:
            try:
                raw_value = input("angle> ").strip()
            except EOFError:
                break
            if raw_value.lower() in {"q", "quit", "exit"}:
                break
            try:
                angle_degrees = float(raw_value)
            except ValueError:
                print("Enter a numeric angle or q.")
                continue
            target_turns = degrees_to_motor_turns(angle_degrees)
            if motor_actions.set_target_position(args.motor, target_turns):
                print(
                    f"Commanded {angle_degrees:g} degrees "
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
        if selected_motor is not None:
            motor_actions.set_axis_state(args.motor, MotorState.IDLE)
        if configured and can_actions is not None:
            for bus_name in list(can_actions.ctx.store):
                try:
                    can_actions.close(bus_name)
                except (OSError, ValueError):
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
