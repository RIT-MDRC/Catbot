"""CPU policy inference and state, independent of ROS and simulation packages."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import torch

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


def finite_tensor(values, size: int, name: str) -> torch.Tensor:
    """Validate a flat numeric vector before it enters inference or mapping."""
    try:
        result = torch.tensor(values, dtype=torch.float32)
    except (TypeError, ValueError, RuntimeError) as error:
        raise ValueError(f"Invalid {name}") from error
    if result.shape != (size,) or not torch.isfinite(result).all():
        raise ValueError(f"{name} must contain {size} finite values")
    return result


class ActuatorMapping:
    """Map model angles to provisional, bounded hardware logical degrees."""

    def __init__(self, path: Path | None = None):
        path = path or Path(__file__).with_name("default_mapping.json")
        data = json.loads(path.read_text())
        self.names = data["actuator_names"]
        if (
            not isinstance(self.names, list)
            or len(self.names) != 12
            or any(not isinstance(name, str) or not name.strip() for name in self.names)
            or len(set(self.names)) != 12
        ):
            raise ValueError("Mapping must contain 12 unique actuator names")
        self.signs = finite_tensor(data["signs"], 12, "signs")
        self.offsets = finite_tensor(data["offsets_degrees"], 12, "offsets_degrees")
        self.minimum = finite_tensor(data["minimum_degrees"], 12, "minimum_degrees")
        self.maximum = finite_tensor(data["maximum_degrees"], 12, "maximum_degrees")
        if not ((self.signs == 1) | (self.signs == -1)).all():
            raise ValueError("Mapping signs must be +1 or -1")
        if not (self.minimum < self.maximum).all():
            raise ValueError("Mapping minimum must be below maximum")

    def convert(self, radians: torch.Tensor) -> list[float]:
        degrees = torch.rad2deg(radians) * self.signs + self.offsets
        return degrees.clamp(self.minimum, self.maximum).tolist()


def validate_metadata(metadata: dict) -> tuple[dict, dict]:
    """Reject incompatible interfaces before loading the trusted actor."""
    if metadata["schema_version"] != 1:
        raise ValueError("Unsupported policy bundle schema")
    if metadata["torch_version"] != torch.__version__.split("+")[0]:
        raise ValueError("Policy bundle and runtime PyTorch versions must match")
    for key in ("model_sha256", "policy_sha256"):
        digest = metadata[key]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"Invalid {key}")
        try:
            int(digest, 16)
        except ValueError as error:
            raise ValueError(f"Invalid {key}") from error
    contract = metadata["policy_contract"]
    expected = {
        "version": 3,
        "observations": [
            {"name": name, "size": size} for name, size in OBSERVATION_FIELDS
        ],
        "observation_dimension": 90,
        "actions": ACTION_NAMES,
        "joint_order": ["base_free", *ACTION_NAMES],
        "nq": 19,
        "nv": 18,
        "commands": ["forward_mps", "left_mps", "yaw_radps"],
    }
    if any(contract[key] != value for key, value in expected.items()):
        raise ValueError("Incompatible policy observation/action contract")
    ranges = contract["control_ranges"]
    if not isinstance(ranges, list) or len(ranges) != 12:
        raise ValueError("Expected 12 actuator control ranges")
    for limits in ranges:
        bounds = finite_tensor(limits, 2, "control range")
        if bounds[0] > bounds[1]:
            raise ValueError("Control ranges must be ordered")
    if contract["locked_channels"] != [
        i for i, (lo, hi) in enumerate(ranges) if lo == hi
    ]:
        raise ValueError("Locked channels do not match control ranges")
    dt = contract["control_timestep"]
    settings = metadata["settings"]
    for name in (
        "action_smoothing",
        "trot_speed",
        "bound_speed",
        "gait_transition_seconds",
        "air_time_limit",
    ):
        value = settings[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Invalid deployment setting: {name}")
    if (
        isinstance(dt, bool)
        or not isinstance(dt, (float, int))
        or not math.isfinite(dt)
        or dt <= 0
        or not 0 <= settings["action_smoothing"] < 1
        or not 0 <= settings["trot_speed"] < settings["bound_speed"]
        or settings["gait_transition_seconds"] <= 0
        or settings["air_time_limit"] <= 0
    ):
        raise ValueError("Invalid policy timing, smoothing, or gait settings")
    return contract, settings


class PolicyRuntime:
    """Assemble observations, publish one command, then advance local history."""

    def __init__(
        self, bundle: Path, mapping: Path | None = None, feedback_timeout: float = 0.25
    ):
        if not math.isfinite(feedback_timeout) or feedback_timeout <= 0:
            raise ValueError("feedback_timeout must be finite and positive")
        self.metadata = json.loads((bundle / "policy.json").read_text())
        try:
            self.contract, self.settings = validate_metadata(self.metadata)
        except (KeyError, TypeError, IndexError) as error:
            raise ValueError("Malformed policy bundle metadata") from error
        policy_path = bundle / "policy.pt"
        if (
            hashlib.sha256(policy_path.read_bytes()).hexdigest()
            != self.metadata["policy_sha256"]
        ):
            raise ValueError("Policy checksum does not match metadata")
        torch.set_num_threads(1)
        self.actor = torch.jit.load(str(policy_path), map_location="cpu").eval()
        self.mapping = ActuatorMapping(mapping)
        self.dt = self.contract["control_timestep"]
        ranges = torch.tensor(self.contract["control_ranges"], dtype=torch.float32)
        self.center = ranges.mean(dim=1)
        self.half_range = (ranges[:, 1] - ranges[:, 0]) / 2
        self.command = torch.zeros(3)
        self.previous_action = torch.zeros(12)
        self.previous_action_delta = torch.zeros(12)
        self.gait_phase = 0.0
        self.gait_blend = 0.0
        self.feedback = None
        self.feedback_received = float("-inf")
        self.feedback_timeout = feedback_timeout
        with torch.inference_mode():
            self._validate_action(self.actor(torch.zeros(1, 90)))

    @staticmethod
    def _validate_action(action):
        if (
            not isinstance(action, torch.Tensor)
            or action.shape != (1, 12)
            or not torch.isfinite(action).all()
        ):
            raise ValueError("Policy must return 12 finite actions with shape (1, 12)")

    def set_command(self, values) -> None:
        self.command = finite_tensor(values, 3, "velocity command")

    def update_feedback(self, values: dict, now: float) -> None:
        # An invalid replacement invalidates the previous sample immediately.
        self.feedback = None
        blocks = {}
        for name, size in FEEDBACK_FIELDS:
            value = values[name]
            blocks[name] = finite_tensor(
                [value] if name == "motion_progress" else value, size, name
            )
        self.feedback = blocks
        self.feedback_received = now

    def observation(self) -> torch.Tensor:
        if self.feedback is None:
            raise ValueError("No valid feedback")
        blocks = {
            **self.feedback,
            "command": self.command,
            "previous_action": self.previous_action,
            "previous_action_delta": self.previous_action_delta,
            "gait_sin": torch.tensor([math.sin(2 * math.pi * self.gait_phase)]),
            "gait_cos": torch.tensor([math.cos(2 * math.pi * self.gait_phase)]),
            "gait_blend": torch.tensor([self.gait_blend]),
        }
        return torch.cat([blocks[name] for name, _ in OBSERVATION_FIELDS]).unsqueeze(0)

    def step(self, now: float, publish) -> bool:
        """Publish if feedback is fresh; commit history only after successful send."""
        if (
            self.feedback is None
            or not 0 <= now - self.feedback_received <= self.feedback_timeout
        ):
            return False
        with torch.inference_mode():
            raw_action = self.actor(self.observation())
            self._validate_action(raw_action)
            smoothing = self.settings["action_smoothing"]
            action = smoothing * self.previous_action + (1 - smoothing) * raw_action[
                0
            ].clamp(-1, 1)
            action = action * (self.half_range > 0)
            targets = self.mapping.convert(self.center + action * self.half_range)
        publish(list(self.mapping.names), targets)
        self.previous_action_delta = action - self.previous_action
        self.previous_action = action
        target_blend = min(
            1.0,
            max(
                0.0,
                (abs(self.command[0].item()) - self.settings["trot_speed"])
                / (self.settings["bound_speed"] - self.settings["trot_speed"]),
            ),
        )
        limit = self.dt / self.settings["gait_transition_seconds"]
        self.gait_blend += min(limit, max(-limit, target_blend - self.gait_blend))
        moving = (
            self.command[:2].norm().item() > 0.1 or abs(self.command[2].item()) > 0.1
        )
        self.gait_phase = (
            self.gait_phase + self.dt * (1.5 + 0.5 * self.gait_blend) * moving
        ) % 1.0
        return True
