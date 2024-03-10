from dataclasses import dataclass
from time import sleep

from state_management import (
    create_generic_context,
    device_action,
    device_attr,
    device_parser,
)

from .pin import direction_pin_action, speed_pin_action


@device_attr(speed_pin_action.ctx, "speed")
@device_attr(direction_pin_action.ctx, "direction")
@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    speed: str
    direction: str
    stop_duration: float


ctx = create_generic_context("raw_motor", [RawMotor])


@device_parser(ctx)
def parse_raw_motor(data: dict) -> RawMotor:
    """Parse a raw motor from a dictionary."""
    return RawMotor(**data)


@device_action(ctx)
def set_speed(raw_motor: RawMotor, speed: float) -> bool:
    """Set the speed of a raw motor. The absolute value of the speed will be used."""
    return speed_pin_action.set(raw_motor.speed, speed) == abs(speed)


@device_action(ctx)
def stop(raw_motor: RawMotor, wait: bool = False) -> bool:
    """Stop a raw motor."""
    isStopped = speed_pin_action.stop(raw_motor.speed) == 0.0
    if wait:
        sleep(raw_motor.stop_duration)
    return isStopped


@device_action(ctx)
def get_speed(raw_motor: RawMotor) -> float:
    """Get the speed of a raw motor."""
    return speed_pin_action.get(raw_motor.speed)


@device_action(ctx)
def check_direction(raw_motor: RawMotor, direction: int) -> bool:
    """Check the direction of a raw motor."""
    return direction_pin_action.check_direction(raw_motor.direction, direction)


@device_action(ctx)
def get_direction(raw_motor: RawMotor) -> int:
    """Get the direction of a raw motor.
    Don't use this function to check the direction of a raw motor. Use `check_direction` instead.
    """
    return direction_pin_action.get_direction(raw_motor.direction)


@device_action(ctx)
def set_direction(raw_motor: RawMotor, direction: int) -> bool:
    """Set the direction of a raw motor."""
    if check_direction(raw_motor, direction):
        return True
    if not get_speed(raw_motor) == 0 and stop(raw_motor, True):
        raise ValueError("Failed to stop the motor")
    return direction_pin_action.set_direction(raw_motor.direction, direction)


@device_action(ctx)
def set_speed_direction(raw_motor: RawMotor, value: float) -> bool:
    """Set the speed and direction of a raw motor."""
    print(f"Setting speed and direction {raw_motor} {value}")
    if value == 0:
        return stop(raw_motor)
    direction = value < 0
    if not set_direction(raw_motor, int(direction)):
        return False
    return set_speed(raw_motor, value)
