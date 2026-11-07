"""Validation and conversion helpers for sparse body position commands."""

import math

MOTOR_TURNS_PER_ACTUATOR_TURN = 64.0


def degrees_to_motor_turns(degrees: float) -> float:
    """Convert a joint angle in degrees to the current ODrive motor-turn scale."""
    return degrees * MOTOR_TURNS_PER_ACTUATOR_TURN / 360.0


def motors_by_axis_id(motors: dict) -> list[tuple[str, object]]:
    """Return configured motors in deterministic CAN axis-ID order."""
    ordered = sorted(motors.items(), key=lambda item: (item[1].axisID, item[0]))
    axis_ids = [motor.axisID for _, motor in ordered]
    if len(axis_ids) != len(set(axis_ids)):
        raise ValueError("Configured ODrive CAN axis IDs must be unique")
    return ordered


def prepare_position_targets(
    actuator_names: list[str],
    positions_degrees: list[float],
    motors: dict,
    ready_motor_names: set[str],
) -> list[tuple[str, float]]:
    """Validate a sparse command completely before returning motor-turn targets."""
    if not actuator_names:
        raise ValueError("Position command must name at least one actuator")
    if len(actuator_names) != len(positions_degrees):
        raise ValueError(
            "actuator_names and positions_degrees must have the same length"
        )
    if len(actuator_names) != len(set(actuator_names)):
        raise ValueError("Position command contains duplicate actuator names")

    targets = []
    for name, degrees in zip(actuator_names, positions_degrees):
        motor = motors.get(name)
        if motor is None:
            raise ValueError(f'Unknown actuator "{name}"')
        if name not in ready_motor_names:
            raise ValueError(f'Actuator "{name}" is not ready for position control')
        if motor.axis_error:
            raise ValueError(
                f'Actuator "{name}" has ODrive axis error 0x{motor.axis_error:x}'
            )
        if not math.isfinite(degrees):
            raise ValueError(f'Actuator "{name}" has a non-finite position')

        target_turns = degrees_to_motor_turns(degrees)
        if motor.position_min is not None and target_turns < motor.position_min:
            raise ValueError(
                f'Actuator "{name}" target is below its configured lower bound'
            )
        if motor.position_max is not None and target_turns > motor.position_max:
            raise ValueError(
                f'Actuator "{name}" target is above its configured upper bound'
            )
        targets.append((name, target_turns))

    return targets
