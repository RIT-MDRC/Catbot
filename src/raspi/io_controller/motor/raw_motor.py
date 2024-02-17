from dataclasses import dataclass

from raspi.state_management import create_device_store


@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    speed: str
    direction: str


(raw_motor_action,) = create_device_store("raw_motor", [RawMotor])


@raw_motor_action
def set_speed(raw_motor: RawMotor, speed: float):
    """Set the speed of a raw motor."""
