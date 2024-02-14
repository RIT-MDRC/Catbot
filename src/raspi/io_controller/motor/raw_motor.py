from dataclasses import dataclass

from ...state_management.device import create_component_store


@dataclass(slots=True)
class RawMotor:
    """A data class for a raw motor."""

    speed: str
    direction: str


(raw_motor_action,) = create_component_store("raw_motor", [RawMotor])


@raw_motor_action
def set_speed(raw_motor: RawMotor, speed: float):
    """Set the speed of a raw motor."""
