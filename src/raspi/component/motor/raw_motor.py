from asyncio import sleep
from dataclasses import dataclass

from gpiozero import DigitalOutputDevice, PWMOutputDevice
from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from .pin import direction_pin_action, speed_pin_action


@device
@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    stop_duration: float
    speed: PWMOutputDevice = identifier(speed_pin_action.ctx)
    direction: DigitalOutputDevice = identifier(direction_pin_action.ctx)


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
def get_speed(raw_motor: RawMotor) -> float:
    """Get the speed of a raw motor."""
    return speed_pin_action.get(raw_motor.speed)


@device_action(ctx)
async def stop(raw_motor: RawMotor) -> bool:
    """Stop a raw motor."""
    speed_pin_action.stop(raw_motor.speed) == 0.0
    await sleep(raw_motor.stop_duration)
    return get_speed(raw_motor) == 0.0


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
async def set_direction(raw_motor: RawMotor, direction: int) -> bool:
    """Set the direction of a raw motor."""
    if check_direction(raw_motor, direction):
        return True
    if not get_speed(raw_motor) == 0 and not await stop(raw_motor):
        raise ValueError("Failed to stop the motor")
    return direction_pin_action.set_direction(raw_motor.direction, direction)


@device_action(ctx)
async def set_speed_direction(raw_motor: RawMotor, value: float) -> bool:
    """Set the speed and direction of a raw motor.
    value: the speed of the motor in percentage (-100 to 100)
    """
    if value == 0:
        return await stop(raw_motor)
    direction = value < 0
    if not await set_direction(raw_motor, int(direction)):
        return False
    return set_speed(raw_motor, value)
