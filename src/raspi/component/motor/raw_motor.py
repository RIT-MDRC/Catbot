import logging
from asyncio import sleep
from dataclasses import dataclass, field

from gpiozero import PWMOutputDevice
from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from .pin import speed_pin_action


@device
@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    stop_duration: float
    stop_duty_cycle: float
    min_duty_cycle: float
    speed: PWMOutputDevice = identifier(speed_pin_action.ctx)
    cached_range: float = field(
        default=None
    )  # This is automatically calculated by the system
    cached_raw_half_range: float = field(default=None)


ctx = create_generic_context("raw_motor", [RawMotor])


@device_parser(ctx)
def parse_raw_motor(data: dict) -> RawMotor:
    """Parse a raw motor from a dictionary."""
    motor = RawMotor(**data)
    if motor.cached_range is None:
        motor.cached_range = 50 / (
            motor.stop_duty_cycle - motor.min_duty_cycle
        )  # * 2 /100 to get the speed in percentage
    if motor.cached_raw_half_range is None:
        motor.cached_raw_half_range = motor.stop_duty_cycle - motor.min_duty_cycle
    return motor


@device_action(ctx)
def check_direction(device: RawMotor, direction: int) -> bool:
    """Check the direction of a raw motor."""
    return speed_pin_action.get(device.speed) > device.min_duty_cycle == direction


@device_action(ctx)
def check_speed(device: RawMotor, speed: float) -> bool:
    return speed_pin_action.check_speed(device.speed, speed)


@device_action(ctx)
def get_speed(device: RawMotor) -> float:
    """Get the speed of a raw motor."""
    return speed_pin_action.get(device.speed)


@device_action(ctx)
def get_speed_percentage(device: RawMotor) -> float:
    """Get the speed of a raw motor."""
    return (
        speed_pin_action.get(device.speed)
        - device.min_duty_cycle
        - device.stop_duty_cycle
    ) * device.cached_range


@device_action(ctx)
async def stop(device: RawMotor) -> bool:
    """Stop a raw motor."""
    logging.info("Stopping motor")
    speed_pin_action.set(device.speed, device.stop_duty_cycle)
    await sleep(device.stop_duration)
    return speed_pin_action.check_speed(device.speed, device.stop_duty_cycle)


@device_action(ctx)
async def set_speed(device: RawMotor, speed: float) -> bool:
    """Set the speed of a raw motor."""
    logging.info("setting speed %s", speed)
    if speed < device.min_duty_cycle or speed > device.stop_duty_cycle + (
        device.cached_raw_half_range
    ):
        logging.error("Speed out of range got %s", speed)
        return False
    speed_pin_action.set(device.speed, speed)
    return speed_pin_action.check_speed(device.speed, speed)


@device_action(ctx)
async def set_speed_percentage(device: RawMotor, speed: float) -> bool:
    """Set the speed of a raw motor. speed range: -100% ~ 100%."""
    logging.info("setting speed percent %s", speed)
    if speed < -100 or speed > 100:
        logging.error("Speed out of range got %s", speed)
        return False
    duty_cycle = abs(speed) / 100 * device.cached_raw_half_range
    direction = speed > 0
    if not direction:
        duty_cycle = -duty_cycle
    speed_pin_action.set(device.speed, duty_cycle + device.stop_duty_cycle)


@device_action(ctx)
def get_direction(device: RawMotor) -> float:
    """Get the direction of a raw motor.
    Don't use this function to check the direction of a raw motor. Use `check_direction` instead.
    """
    return speed_pin_action.get(device.speed)
