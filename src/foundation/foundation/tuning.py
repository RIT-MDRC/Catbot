"""Validation of operator-provided ODrive baselines and bounded gain scaling."""

import math


def validate_tuning(values):
    for name, value in values.items():
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        if name == "policy_gain_scale" or name.endswith(".gain_scale"):
            if not 0.1 <= value <= 1:
                raise ValueError(f"{name} must be in [0.1, 1]")
        elif name.endswith(("speed_motor_turns_s", "accel_motor_turns_s2")):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        elif (
            name.endswith(("position_gain", "velocity_gain", "integrator_gain"))
            and value < 0
        ):
            raise ValueError(
                f"{name} requires an explicit nonnegative firmware baseline"
            )
