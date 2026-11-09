"""Hardware-free inference, contract, feedback, and actuator mapping checks."""

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import torch

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
        self.runtime = PolicyRuntime(self.root)
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

    def test_clamping_smoothing_names_mapping_and_history(self):
        self.runtime.update_feedback(feedback_values(), 0)
        self.assertTrue(self.runtime.step(0, self.publish))
        names, targets = self.commands[0]
        self.assertEqual(
            names,
            [
                "fla",
                "flf",
                "flk",
                "fra",
                "frf",
                "frk",
                "bla",
                "blf",
                "blk",
                "bra",
                "brf",
                "brk",
            ],
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

    def test_mapping_overrides_and_bounds(self):
        default = Path(__file__).parents[1] / "catbot_policy" / "default_mapping.json"
        mapping = json.loads(default.read_text())
        mapping["signs"][0] = -1
        mapping["offsets_degrees"][0] = 5
        path = self.root / "mapping.json"
        path.write_text(json.dumps(mapping))
        converted = ActuatorMapping(path).convert(torch.full((12,), math.pi / 2))
        self.assertEqual(converted[0], -40)
        self.assertEqual(converted[2], 55)
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
                PolicyRuntime(self.root)
        metadata_path.write_text(json.dumps(original))
        (self.root / "policy.pt").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            PolicyRuntime(self.root)

    def test_locked_channel_is_masked(self):
        path = self.root / "policy.json"
        metadata = json.loads(path.read_text())
        metadata["policy_contract"]["control_ranges"][0] = [0.1, 0.1]
        metadata["policy_contract"]["locked_channels"] = [0]
        path.write_text(json.dumps(metadata))
        runtime = PolicyRuntime(self.root)
        runtime.update_feedback(feedback_values(), 0)
        runtime.step(0, self.publish)
        self.assertEqual(runtime.previous_action[0].item(), 0)
        self.assertAlmostEqual(self.commands[0][1][0], math.degrees(0.1), places=5)


if __name__ == "__main__":
    unittest.main()
