"""Hardware-free inference, contract, feedback, and actuator mapping checks."""

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from mapping_fixture import write_mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catbot_policy.runtime import (
    ACTION_NAMES,
    FEEDBACK_FIELDS,
    OBSERVATION_FIELDS,
    ActuatorMapping,
    PolicyRuntime,
)


class ConstantActor(torch.nn.Module):
    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return torch.ones_like(obs[:, :12]) * 2


def make_bundle(root: Path) -> Path:
    torch.jit.script(ConstantActor()).save(str(root / "policy.pt"))
    metadata = {
        "schema_version": 1,
        "torch_version": torch.__version__.split("+")[0],
        "policy_sha256": hashlib.sha256((root / "policy.pt").read_bytes()).hexdigest(),
        "model_sha256": "0" * 64,
        "policy_contract": {
            "version": 3,
            "observations": [{"name": n, "size": s} for n, s in OBSERVATION_FIELDS],
            "observation_dimension": 90,
            "actions": ACTION_NAMES,
            "joint_order": ["base_free", *ACTION_NAMES],
            "nq": 19,
            "nv": 18,
            "commands": ["forward_mps", "left_mps", "yaw_radps"],
            "control_ranges": [[-0.7, 0.7], [-0.7, 0.7], [-math.pi, 0]] * 4,
            "locked_channels": [],
            "control_timestep": 0.02,
        },
        "settings": {
            "action_smoothing": 0.8,
            "trot_speed": 0.35,
            "bound_speed": 0.6,
            "gait_transition_seconds": 0.5,
            "air_time_limit": 0.5,
        },
    }
    (root / "policy.json").write_text(json.dumps(metadata))
    return root


def feedback_values() -> dict:
    values: dict = {name: [0.0] * size for name, size in FEEDBACK_FIELDS}
    values["base_height_quaternion"] = [0.4, 1.0, 0.0, 0.0, 0.0]
    values["motion_progress"] = 0.0
    return values


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = make_bundle(Path(self.temporary.name))
        self.mapping = write_mapping(self.root)
        self.runtime = PolicyRuntime(self.root, mapping=self.mapping)
        self.commands = []

    def publish(self, names, targets):
        self.commands.append((names, targets))

    def test_observation_order_and_software_fields(self):
        feedback = feedback_values()
        for index, (name, size) in enumerate(FEEDBACK_FIELDS):
            feedback[name] = [float(index)] * size if size > 1 else float(index)
        self.runtime.update_feedback(feedback, 10.0)
        self.runtime.set_command([0.8, -0.2, 0.5])
        obs = self.runtime.observation()[0]
        offset = 0
        for name, size in OBSERVATION_FIELDS:
            block = obs[offset : offset + size]
            offset += size
            if name in feedback:
                value = feedback[name]
                expected = [value] if name == "motion_progress" else value
                torch.testing.assert_close(block, torch.tensor(expected))
            elif name == "command":
                torch.testing.assert_close(block, torch.tensor([0.8, -0.2, 0.5]))
            elif name == "gait_cos":
                self.assertEqual(block.item(), 1)
            else:
                self.assertEqual(block.abs().sum().item(), 0)
        self.assertEqual(offset, 90)

    def test_observation_storage_reused_and_command_update_atomic(self):
        self.runtime.update_feedback(feedback_values(), 0)
        original = self.runtime.observation()
        self.runtime.set_command([0.8, -0.2, 0.5])
        cached = self.runtime.command_values
        with self.assertRaises(ValueError):
            self.runtime.set_command([float("nan"), 0, 0])
        self.assertEqual(cached, self.runtime.command_values)
        self.runtime.step(0, self.publish)
        updated = self.runtime.observation()
        self.assertEqual(original.data_ptr(), updated.data_ptr())
        offset = 0
        for name, size in OBSERVATION_FIELDS:
            block = updated[0, offset : offset + size]
            if name == "previous_action":
                torch.testing.assert_close(block, self.runtime.previous_action)
            if name == "gait_sin":
                self.assertAlmostEqual(
                    block.item(),
                    math.sin(2 * math.pi * self.runtime.gait_phase),
                    places=6,
                )
            offset += size

    def test_clamping_smoothing_names_mapping_and_history(self):
        self.runtime.update_feedback(feedback_values(), 0)
        self.assertTrue(self.runtime.step(0, self.publish))
        names, targets = self.commands[0]
        self.assertEqual(
            names,
            [f"joint_{i}" for i in range(12)],
        )
        self.assertAlmostEqual(targets[0], math.degrees(0.14), places=5)
        self.assertAlmostEqual(targets[2], 18, places=4)
        torch.testing.assert_close(self.runtime.previous_action, torch.full((12,), 0.2))
        torch.testing.assert_close(
            self.runtime.previous_action_delta, torch.full((12,), 0.2)
        )
        self.runtime.step(0.02, self.publish)
        torch.testing.assert_close(
            self.runtime.previous_action, torch.full((12,), 0.36)
        )
        torch.testing.assert_close(
            self.runtime.previous_action_delta, torch.full((12,), 0.16)
        )
        for index in range(20):
            self.runtime.update_feedback(feedback_values(), index + 1)
            self.runtime.step(index + 1, self.publish)
        self.assertEqual(self.commands[-1][1][2], 55)

    def test_missing_stale_invalid_feedback_freezes_history(self):
        self.assertFalse(self.runtime.step(1, self.publish))
        self.runtime.update_feedback(feedback_values(), 1)
        self.assertFalse(self.runtime.step(1.251, self.publish))
        self.assertEqual(self.commands, [])
        for name, size in FEEDBACK_FIELDS:
            invalid = feedback_values()
            invalid[name] = math.nan if size == 1 else [math.nan] * size
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.runtime.update_feedback(invalid, 2)
            self.assertFalse(self.runtime.step(2, self.publish))
        self.assertEqual(self.runtime.previous_action.abs().sum().item(), 0)
        self.assertEqual(self.runtime.gait_phase, 0)
        self.runtime.update_feedback(feedback_values(), 3)
        self.assertTrue(self.runtime.step(3, self.publish))

    def test_wrong_feedback_shapes_and_commands_are_rejected(self):
        for values in ([0.0] * 11, [[0.0] * 12], "invalid"):
            invalid = feedback_values()
            invalid["joint_positions"] = values
            with self.assertRaises(ValueError):
                self.runtime.update_feedback(invalid, 0)
        for command in ([math.inf, 0, 0], [0, 0], [1e100, 0, 0]):
            with self.assertRaises(ValueError):
                self.runtime.set_command(command)

    def test_gait_tracks_command_and_freezes_at_rest(self):
        self.runtime.update_feedback(feedback_values(), 0)
        self.runtime.step(0, self.publish)
        self.assertEqual(self.runtime.gait_phase, 0)
        self.runtime.set_command([0.8, 0, 0])
        self.runtime.step(0.02, self.publish)
        self.assertAlmostEqual(self.runtime.gait_blend, 0.04)
        self.assertAlmostEqual(self.runtime.gait_phase, 0.02 * 1.52)
        phase = self.runtime.gait_phase
        self.runtime.set_command([0, 0, 0])
        self.runtime.step(0.04, self.publish)
        self.assertEqual(self.runtime.gait_phase, phase)
        self.assertAlmostEqual(self.runtime.gait_blend, 0)
        self.runtime.set_command([0, 0, 0.5])
        self.runtime.step(0.06, self.publish)
        self.assertAlmostEqual(self.runtime.gait_phase, phase + 0.03)

    def test_failed_inference_or_publish_does_not_commit_history(self):
        self.runtime.update_feedback(feedback_values(), 0)
        for output in (torch.zeros(1, 16), torch.full((1, 12), math.nan)):
            self.runtime.actor = lambda _, result=output: result
            with self.assertRaises(ValueError):
                self.runtime.step(0, self.publish)
        self.runtime.actor = lambda _: torch.ones(1, 12)

        def fail(*_):
            raise RuntimeError("publisher failed")

        with self.assertRaises(RuntimeError):
            self.runtime.step(0, fail)
        self.assertEqual(self.runtime.previous_action.sum().item(), 0)
        self.assertEqual(self.commands, [])

    def test_invalid_runtime_options_rejected_before_loading_actor(self):
        for options, message in (
            ({"feedback_timeout": 0}, "feedback_timeout"),
            ({"feedback_timeout": math.inf}, "feedback_timeout"),
            ({"device": "meta"}, "policy_device"),
            ({"torch_compatibility": "auto"}, "torch_compatibility"),
        ):
            with (
                self.subTest(options=options),
                patch("torch.jit.load") as load,
                self.assertRaisesRegex(ValueError, message),
            ):
                PolicyRuntime(self.root, mapping=self.mapping, **options)
            load.assert_not_called()

    def test_cuda_without_available_runtime_rejected_before_loading_actor(self):
        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.jit.load") as load,
            self.assertRaisesRegex(ValueError, "no usable CUDA"),
        ):
            PolicyRuntime(self.root, mapping=self.mapping, device="cuda:0")
        load.assert_not_called()

    def test_incompatible_actor_load_reports_export_and_runtime_versions(self):
        path = self.root / "policy.json"
        metadata = json.loads(path.read_text())
        metadata["torch_version"] = "0.0.0"
        path.write_text(json.dumps(metadata))
        with (
            patch("torch.jit.load", side_effect=RuntimeError("unsupported archive")),
            self.assertWarnsRegex(RuntimeWarning, "not numerical parity"),
            self.assertRaises(ValueError) as error,
        ):
            PolicyRuntime(self.root, mapping=self.mapping, torch_compatibility="load")
        self.assertIn("exported with PyTorch 0.0.0", str(error.exception))
        self.assertIn(f"using {torch.__version__}", str(error.exception))
        self.assertIsInstance(error.exception.__cause__, RuntimeError)

    def test_mapping_overrides_and_bounds(self):
        mapping = json.loads(self.mapping.read_text())
        mapping["signs"][0] = -1
        mapping["offsets_degrees"][0] = 5
        path = self.root / "mapping.json"
        path.write_text(json.dumps(mapping))
        converter = ActuatorMapping(path)
        converted = converter.convert(torch.full((12,), math.pi / 6))
        self.assertAlmostEqual(converted[0], -25, places=4)
        self.assertAlmostEqual(converted[1], 30, places=4)
        self.assertEqual(converted[2], 55)
        self.assertEqual(converter.convert(torch.full((12,), 10.0))[0], -40)
        self.assertEqual(converter.convert(torch.full((12,), -10.0))[0], 40)
        mapping["actuator_names"][0] = mapping["actuator_names"][1]
        path.write_text(json.dumps(mapping))
        with self.assertRaisesRegex(ValueError, "unique"):
            ActuatorMapping(path)

    def test_contract_and_checksum_rejection(self):
        metadata_path = self.root / "policy.json"
        original = json.loads(metadata_path.read_text())
        for key, value in (
            ("actions", ACTION_NAMES[::-1]),
            ("observation_dimension", 110),
            ("observations", original["policy_contract"]["observations"][::-1]),
            ("control_timestep", 0),
        ):
            metadata = json.loads(json.dumps(original))
            metadata["policy_contract"][key] = value
            metadata_path.write_text(json.dumps(metadata))
            with self.subTest(key=key), self.assertRaises(ValueError):
                PolicyRuntime(self.root, mapping=self.mapping)
        metadata_path.write_text(json.dumps(original))
        (self.root / "policy.pt").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            PolicyRuntime(self.root, mapping=self.mapping)

    def test_locked_channel_is_masked(self):
        path = self.root / "policy.json"
        metadata = json.loads(path.read_text())
        metadata["policy_contract"]["control_ranges"][0] = [0.1, 0.1]
        metadata["policy_contract"]["locked_channels"] = [0]
        path.write_text(json.dumps(metadata))
        runtime = PolicyRuntime(self.root, mapping=self.mapping)
        runtime.update_feedback(feedback_values(), 0)
        runtime.step(0, self.publish)
        self.assertEqual(runtime.previous_action[0].item(), 0)
        self.assertAlmostEqual(self.commands[0][1][0], math.degrees(0.1), places=5)


if __name__ == "__main__":
    unittest.main()
