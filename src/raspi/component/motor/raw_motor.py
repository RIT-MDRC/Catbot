from dataclasses import dataclass

from raspi.state_management import create_device_store

from .speed_pin import speed_pin_attr


@speed_pin_attr("speed")
@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    speed: str
    direction: str


(raw_motor_action, _, raw_motor_attr) = create_device_store("raw_motor", [RawMotor])

__all__ = ["set_speed", "RawMotor", "raw_motor_attr"]


@raw_motor_action
def set_speed(raw_motor: RawMotor, speed: float) -> None:
    """Set the speed of a raw motor."""
    raw_motor.speed = speed
