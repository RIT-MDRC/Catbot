"""Pure helpers for converting and describing ODrive body state."""

import math
from enum import IntFlag

from body_control import MOTOR_TURNS_PER_30_DEGREES


def motor_turns_to_degrees(turns: float) -> float:
    """Convert the current ODrive motor-turn scale to joint degrees."""
    return turns * 30.0 / MOTOR_TURNS_PER_30_DEGREES


def kinematic_values(motor, now: float, stale_seconds: float) -> tuple:
    """Return validity, position, and velocity for one motor estimate."""
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
        motor_turns_to_degrees(motor.current_position),
        motor_turns_to_degrees(motor.current_velocity),
    )


def heartbeat_available(motor, now: float, stale_seconds: float) -> bool:
    """Return whether a recent heartbeat has been received."""
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
