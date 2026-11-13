"""JSON protocol and sensor contract shared by ROS and inference Python versions."""

import math

VERSION = 1
MAX_LINE_BYTES = 131072

# Deliberately checked against the exported contract; changes require a new version.
OBSERVATION_FIELDS = (
    ("base_height_quaternion", 5),
    ("heading_linear_velocity", 3),
    ("base_angular_velocity", 3),
    ("joint_positions", 12),
    ("joint_velocities", 12),
    ("command", 3),
    ("previous_action", 12),
    ("previous_action_delta", 12),
    ("normalized_air_time", 4),
    ("previous_contact", 4),
    ("has_stance", 4),
    ("gait_sin", 1),
    ("gait_cos", 1),
    ("gait_blend", 1),
    ("motion_travel", 12),
    ("motion_progress", 1),
)
ACTION_NAMES = [
    f"{leg}_{joint}"
    for leg in ("fl", "fr", "rl", "rr")
    for joint in ("hip_abduction", "hip_flexion", "knee")
]
LOCAL_FIELDS = {
    "command",
    "previous_action",
    "previous_action_delta",
    "gait_sin",
    "gait_cos",
    "gait_blend",
}
FEEDBACK_FIELDS = tuple(
    (name, size) for name, size in OBSERVATION_FIELDS if name not in LOCAL_FIELDS
)


def finite_values(values, size, name):
    if not isinstance(values, (list, tuple)) or len(values) != size:
        raise ValueError(f"{name} must contain {size} values")
    if any(
        not isinstance(v, (bool, int, float)) or not math.isfinite(v) for v in values
    ):
        raise ValueError(f"{name} must contain finite numeric values")
    return list(values)


def validate_feedback(values):
    if not isinstance(values, dict):
        raise ValueError("Feedback must be a named snapshot")
    result = {}
    for name, size in FEEDBACK_FIELDS:
        value = values[name]
        checked = finite_values(
            [value] if name == "motion_progress" else value, size, name
        )
        result[name] = checked[0] if name == "motion_progress" else checked
    return result
