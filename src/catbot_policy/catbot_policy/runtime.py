"""CPU/CUDA policy inference and state, independent of ROS and simulation packages."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import torch

from catbot_policy.configuration import validate_mapping
from catbot_policy.files import sha256_file
from catbot_policy.protocol import (
    ACTION_NAMES,
    FEEDBACK_FIELDS,
    OBSERVATION_DIMENSION,
    OBSERVATION_FIELDS,
)


def finite_tensor(
    values, size: int, name: str, *, device="cpu", allow_bool=False
) -> torch.Tensor:
    """Validate a flat numeric vector before it enters inference or mapping."""
    if (
        isinstance(values, (list, tuple))
        and not allow_bool
        and any(isinstance(value, bool) for value in values)
    ):
        raise ValueError(f"Invalid boolean in {name}")
    if (
        isinstance(values, torch.Tensor)
        and values.dtype == torch.bool
        and not allow_bool
    ):
        raise ValueError(f"Invalid boolean in {name}")
    try:
        result = torch.tensor(values, dtype=torch.float32, device=device)
    except (TypeError, ValueError, RuntimeError, OverflowError) as error:
        raise ValueError(f"Invalid {name}") from error
    if result.shape != (size,) or not torch.isfinite(result).all():
        raise ValueError(f"{name} must contain {size} finite values")
    return result


class ActuatorMapping:
    """Map model angles to provisional, bounded hardware logical degrees."""

    def __init__(self, path: Path | None = None, device="cpu"):
        path = path or Path(__file__).with_name("default_mapping.json")
        data = json.loads(path.read_text())
        self.metadata = data
        self.names = data["actuator_names"]
        validate_mapping(data)
        self.signs = finite_tensor(data["signs"], 12, "signs", device=device)
        self.offsets = finite_tensor(
            data["offsets_degrees"], 12, "offsets_degrees", device=device
        )
        self.minimum = finite_tensor(
            data["minimum_degrees"], 12, "minimum_degrees", device=device
        )
        self.maximum = finite_tensor(
            data["maximum_degrees"], 12, "maximum_degrees", device=device
        )

    def convert(self, radians: torch.Tensor) -> list[float]:
        degrees = torch.rad2deg(radians) * self.signs + self.offsets
        return degrees.clamp(self.minimum, self.maximum).tolist()


def validate_metadata(metadata: dict) -> tuple[dict, dict]:
    """Reject malformed or incompatible metadata with a consistent ValueError."""
    try:
        return _validate_metadata(metadata)
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError("Malformed policy bundle metadata") from error


def _validate_metadata(metadata: dict) -> tuple[dict, dict]:
    """Reject incompatible interfaces before loading the trusted actor."""
    if type(metadata["schema_version"]) is not int or metadata["schema_version"] != 1:
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
        "observation_dimension": OBSERVATION_DIMENSION,
        "actions": ACTION_NAMES,
        "joint_order": ["base_free", *ACTION_NAMES],
        "nq": 19,
        "nv": 18,
        "commands": ["forward_mps", "left_mps", "yaw_radps"],
    }
    # JSON comparison preserves scalar types: true must not alias integer 1.
    if any(
        json.dumps(contract[key], sort_keys=True) != json.dumps(value, sort_keys=True)
        for key, value in expected.items()
    ):
        raise ValueError("Incompatible policy observation/action contract")
    ranges = contract["control_ranges"]
    if not isinstance(ranges, list) or len(ranges) != 12:
        raise ValueError("Expected 12 actuator control ranges")
    for limits in ranges:
        finite_tensor(limits, 2, "control range")
        if limits[0] > limits[1]:
            raise ValueError("Control ranges must be ordered")
    if any(type(i) is not int for i in contract["locked_channels"]) or contract[
        "locked_channels"
    ] != [i for i, (lo, hi) in enumerate(ranges) if lo == hi]:
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


def validate_action(action):
    if (
        not isinstance(action, torch.Tensor)
        or action.shape != (1, 12)
        or not torch.isfinite(action).all()
    ):
        raise ValueError("Policy must return 12 finite actions with shape (1, 12)")


class PolicyRuntime:
    """Assemble observations, publish one command, then advance local history."""

    def __init__(
        self,
        bundle: Path,
        mapping: Path | None = None,
        feedback_timeout: float = 0.25,
        device: str = "cpu",
    ):
        if not math.isfinite(feedback_timeout) or feedback_timeout <= 0:
            raise ValueError("feedback_timeout must be finite and positive")
        bundle = bundle.expanduser().resolve()
        self.device = torch.device(device)
        if self.device.type not in ("cpu", "cuda"):
            raise ValueError("policy_device must be cpu or cuda[:index]")
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise ValueError(
                "CUDA policy requested but this Python/PyTorch environment has no usable CUDA. "
                "Install a matching JetPack/Python/PyTorch build in the CUDA environment, "
                "or launch with orin_device:=cpu (or policy_device:=cpu)."
            )
        self.metadata = json.loads((bundle / "policy.json").read_text())
        try:
            self.contract, self.settings = validate_metadata(self.metadata)
        except (KeyError, TypeError, IndexError) as error:
            raise ValueError("Malformed policy bundle metadata") from error
        policy_path = bundle / "policy.pt"
        if sha256_file(policy_path) != self.metadata["policy_sha256"]:
            raise ValueError("Policy checksum does not match metadata")
        torch.set_num_threads(1)
        self.actor = torch.jit.load(str(policy_path), map_location=self.device).eval()
        self.mapping = ActuatorMapping(mapping, device=self.device)
        self.dt = self.contract["control_timestep"]
        ranges = torch.tensor(
            self.contract["control_ranges"], dtype=torch.float32, device=self.device
        )
        self.center = ranges.mean(dim=1)
        self.half_range = (ranges[:, 1] - ranges[:, 0]) / 2
        self.command = torch.zeros(3, device=self.device)
        self.command_values = (0.0, 0.0, 0.0)
        self.observation_buffer = torch.empty(
            1, OBSERVATION_DIMENSION, device=self.device
        )
        self.observation_slices = {}
        offset = 0
        for name, size in OBSERVATION_FIELDS:
            self.observation_slices[name] = slice(offset, offset + size)
            offset += size
        self.previous_action = torch.zeros(12, device=self.device)
        self.previous_action_delta = torch.zeros(12, device=self.device)
        self.gait_phase = 0.0
        self.gait_blend = 0.0
        self.feedback = None
        self.feedback_received = float("-inf")
        self.feedback_timeout = feedback_timeout
        with torch.inference_mode():
            validate_action(
                self.actor(torch.zeros(1, OBSERVATION_DIMENSION, device=self.device))
            )

    def set_command(self, values) -> None:
        command = finite_tensor(values, 3, "velocity command")
        self.command_values = tuple(command.tolist())
        self.command.copy_(command)

    def update_feedback(self, values: dict, now: float) -> None:
        # An invalid replacement invalidates the previous sample immediately.
        self.feedback = None
        blocks = {}
        for name, size in FEEDBACK_FIELDS:
            value = values[name]
            blocks[name] = finite_tensor(
                [value] if name == "motion_progress" else value,
                size,
                name,
                device=self.device,
                allow_bool=name in ("previous_contact", "has_stance"),
            )
        self.feedback = blocks
        self.feedback_received = now

    def observation(self) -> torch.Tensor:
        if self.feedback is None:
            raise ValueError("No valid feedback")
        for name, value in self.feedback.items():
            self.observation_buffer[0, self.observation_slices[name]].copy_(value)
        for name in ("command", "previous_action", "previous_action_delta"):
            self.observation_buffer[0, self.observation_slices[name]].copy_(
                getattr(self, name)
            )
        for name, value in (
            ("gait_sin", math.sin(2 * math.pi * self.gait_phase)),
            ("gait_cos", math.cos(2 * math.pi * self.gait_phase)),
            ("gait_blend", self.gait_blend),
        ):
            self.observation_buffer[0, self.observation_slices[name]].fill_(value)
        return self.observation_buffer

    def step(self, now: float, publish) -> bool:
        """Publish if feedback is fresh; commit history only after successful send."""
        if (
            self.feedback is None
            or not 0 <= now - self.feedback_received <= self.feedback_timeout
        ):
            return False
        with torch.inference_mode():
            observation = self.observation()
            inference_started = time.perf_counter()
            raw_action = self.actor(observation)
            if self.device.type == "cuda":
                torch.cuda.synchronize(self.device)
            self.last_inference_seconds = time.perf_counter() - inference_started
            validate_action(raw_action)
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
                (abs(self.command_values[0]) - self.settings["trot_speed"])
                / (self.settings["bound_speed"] - self.settings["trot_speed"]),
            ),
        )
        limit = self.dt / self.settings["gait_transition_seconds"]
        self.gait_blend += min(limit, max(-limit, target_blend - self.gait_blend))
        moving = (
            math.hypot(*self.command_values[:2]) > 0.1
            or abs(self.command_values[2]) > 0.1
        )
        self.gait_phase = (
            self.gait_phase + self.dt * (1.5 + 0.5 * self.gait_blend) * moving
        ) % 1.0
        return True
