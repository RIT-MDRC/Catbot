"""Validation helpers for sparse logical actuator position commands."""

import math
from collections.abc import Collection, Mapping

from component.actuator import actuator_actions
from component.actuator.actuator import Actuator
from component.motor import motor_actions


def actuators_by_axis_id(
    actuators: Mapping[str, Actuator],
) -> list[tuple[str, Actuator]]:
    """Return configured actuators in deterministic CAN axis-ID order."""
    ordered = sorted(
        actuators.items(),
        key=lambda item: (
            motor_actions.get_state_snapshot(item[1].motor).axis_id,
            item[0],
        ),
    )
    axis_ids = [
        motor_actions.get_state_snapshot(actuator.motor).axis_id
        for _, actuator in ordered
    ]
    if len(axis_ids) != len(set(axis_ids)):
        raise ValueError("Configured ODrive CAN axis IDs must be unique")
    return ordered


def actuator_names_by_axis_id(actuator_names: Collection[str]) -> list[str]:
    """Return configured actuator names in deterministic CAN axis-ID order."""
    ordered = sorted(
        actuator_names,
        key=lambda name: (motor_actions.get_state_snapshot(name).axis_id, name),
    )
    axis_ids = [motor_actions.get_state_snapshot(name).axis_id for name in ordered]
    if len(axis_ids) != len(set(axis_ids)):
        raise ValueError("Configured ODrive CAN axis IDs must be unique")
    return ordered


def prepare_position_targets(
    actuator_names: list[str],
    positions_degrees: list[float],
    actuators: Mapping[str, Actuator] | Collection[str],
    ready_actuator_names: set[str],
) -> list[tuple[str, float]]:
    """Validate a sparse command completely before returning logical targets."""
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
        if name not in actuators:
            raise ValueError(f'Unknown actuator "{name}"')
        actuator: Actuator | str
        if isinstance(actuators, Mapping):
            actuator = actuators[name]
            motor_name = actuator.motor
        else:
            actuator = name
            motor_name = name
        if name not in ready_actuator_names:
            raise ValueError(f'Actuator "{name}" is not ready for position control')
        motor = motor_actions.get_state_snapshot(motor_name)
        if motor.axis_error:
            raise ValueError(
                f'Actuator "{name}" has ODrive axis error 0x{motor.axis_error:x}'
            )
        if not math.isfinite(degrees):
            raise ValueError(f'Actuator "{name}" has a non-finite position')

        try:
            actuator_actions.validate_target_position(actuator, degrees)
        except ValueError as error:
            raise ValueError(f'Actuator "{name}" {error}') from error
        targets.append((name, degrees))

    return targets
