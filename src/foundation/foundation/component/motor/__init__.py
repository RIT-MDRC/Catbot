"""
Modules:
- motor_enums
- motor_actions

!DEPRECATED MODULES:
- raw_motor_actions
- speed_pin_action
- step_pin_action
"""

from . import odrive_enums as motor_enums
from . import odrive_motor as motor_actions
from . import raw_motor as raw_motor_actions
from .pin import speed_pin as speed_pin_action
from .pin import step_pin as step_pin_action

__all__ = [
    "raw_motor_actions",
    "motor_actions",
    "motor_enums",
    "speed_pin_action",
    "step_pin_action",
]
