"""Shared policy parameters and mapping validation, without ROS or PyTorch."""

from pathlib import Path

from catbot_policy.protocol import finite_values

POLICY_DEFAULTS = {
    "policy_bundle": "",
    "policy_device": "cpu",
    "policy_worker_environment": "",
    "policy_worker_sync": True,
    "mapping_file": "",
    "simulation_mode": False,
    "feedback_timeout": 0.25,
    "policy_python": "3.14",
    "policy_worker_project": str(Path(__file__).with_name("inference")),
    "policy_uv_executable": "uv",
    "policy_worker_timeout": 2.0,
    "policy_startup_timeout": 120.0,
}
POLICY_PARAMETERS = tuple(POLICY_DEFAULTS)


def validate_mapping(data):
    """Validate the common logical-degree mapping contract before use."""
    names = data["actuator_names"]
    if (
        not isinstance(names, list)
        or len(names) != 12
        or any(not isinstance(name, str) or not name.strip() for name in names)
        or len(set(names)) != 12
    ):
        raise ValueError("Mapping must contain 12 unique actuator names")
    for key in ("signs", "offsets_degrees", "minimum_degrees", "maximum_degrees"):
        finite_values(data[key], 12, key)
    if any(value not in (-1, 1) for value in data["signs"]):
        raise ValueError("Mapping signs must be +1 or -1")
    if any(
        lo >= hi for lo, hi in zip(data["minimum_degrees"], data["maximum_degrees"])
    ):
        raise ValueError("Mapping minimum must be below maximum")
