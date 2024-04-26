import logging
from asyncio import sleep
from dataclasses import dataclass, field

from gpiozero import DigitalOutputDevice
from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from .pin import step_pin_action


@device
@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    high_duration: float = 0  # seconds but can basically be zero.
    low_duration: float = 0  # seconds but can basically be zero.
    step_pin: DigitalOutputDevice = identifier(step_pin_action.step_ctx)
    direction_pin: DigitalOutputDevice = identifier(step_pin_action.direction_ctx)


ctx = create_generic_context("raw_motor", (RawMotor,))


@device_parser(ctx)
def parse_raw_motor(data: dict) -> RawMotor:
    """Parse a raw motor from a dictionary."""
    return RawMotor(**data)


@device_action(ctx)
async def step_1(motor: RawMotor) -> None:
    """Step the motor once."""
    step_pin_action.set_high(motor.step_pin)
    await sleep(motor.high_duration)
    step_pin_action.set_low(motor.step_pin)


@device_action(ctx)
async def step_n(motor: RawMotor, n: int) -> None:
    """Step the motor n times."""
    logging.info("Stepping motor %d times", n)
    direction = n > 0
    set_dir(motor, int(direction))
    logging.info("successfully switched direction")
    for i in range(abs(n)):
        await step_1(motor)
        if i != n - 1:
            await sleep(motor.low_duration)


@device_action(ctx)
def set_dir(motor: RawMotor, direction: int) -> None:
    """Switch the motor direction."""
    logging.debug("Switching motor direction")
    step_pin_action.set_direction(motor.direction_pin, direction)
