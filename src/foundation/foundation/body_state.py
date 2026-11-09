"""Pure helpers for converting and describing ODrive body state."""

import math
from enum import IntFlag

from component.actuator import actuator_actions
from component.motor import motor_actions


def kinematic_values(actuator, now: float, stale_seconds: float) -> tuple:
    """Return logical validity, position, and velocity for one actuator."""
    motor_name = actuator.motor if hasattr(actuator, "motor") else actuator
    motor = motor_actions.get_state_snapshot(motor_name)
    valid = (
        motor.current_position is not None
        and motor.current_velocity is not None
        and motor.last_encoder_estimate_time is not None
        and now - motor.last_encoder_estimate_time <= stale_seconds
    )
    if not valid:
        return False, math.nan, math.nan
    return (
        True,
        actuator_actions.motor_turns_to_position(actuator, motor.current_position),
        actuator_actions.motor_turns_to_velocity(
            actuator,
            motor.current_velocity,
            position_motor_turns=motor.current_position,
        ),
    )


def heartbeat_available(motor, now: float, stale_seconds: float) -> bool:
    """Return whether a recent heartbeat has been received."""
    if hasattr(motor, "profile"):
        motor = motor_actions.get_state_snapshot(motor.motor)
    elif isinstance(motor, str):
        motor = motor_actions.get_state_snapshot(motor)
    return (
        motor.last_heartbeat_time is not None
        and now - motor.last_heartbeat_time <= stale_seconds
    )


def flag_messages(value: int, flag_type: type[IntFlag]) -> list[str]:
    """Describe every known flag and preserve any unknown bits."""
    if value == 0:
        return []
    messages = [flag.name for flag in flag_type if flag.value and value & flag.value]
    known_bits = 0
    for flag in flag_type:
        known_bits |= flag.value
    unknown_bits = value & ~known_bits
    if unknown_bits:
        messages.append(f"UNKNOWN_BITS_0x{unknown_bits:x}")
    return messages
