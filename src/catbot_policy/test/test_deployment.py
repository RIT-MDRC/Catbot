"""Offline checkpoint download, export parity, and selection failure checks."""

import copy
import hashlib
import importlib.util
import io
import json
import shlex
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catbot_policy.deployment import (
    RUN_FILES,
    export_checkpoint,
    latest_checkpoint,
    main,
    prepare_policy,
    select_run,
)
from catbot_policy.runtime import PolicyRuntime
from test_runtime import make_bundle

HAS_RSL = importlib.util.find_spec("rsl_rl") is not None


class FakeFile:
    def __init__(self, path, fail=False):
        self.path = path
        self.name = path.name
        self.fail = fail
        self.downloads = 0

    def download(self, root, replace):
        self.downloads += 1
        if self.fail:
            raise OSError("Interrupted download")
        target = Path(root) / self.name
        shutil.copyfile(self.path, target)
        return target.open("rb")


class FakeRun:
    def __init__(self, files, run_id="run1"):
        self.id = run_id
        self.saved_files = files

    def files(self):
        return self.saved_files


class FakeApi:
    default_entity = "team"

    def __init__(self, runs):
        self.saved_runs = runs
        self.request = None

    def runs(self, project, order):
        self.request = (project, order)
        return self.saved_runs

    def run(self, path):
        return self.saved_runs[0]


class SelectionTests(unittest.TestCase):
    def test_newest_complete_run_and_numeric_checkpoint(self):
        incomplete = FakeRun([FakeFile(Path("model_999.pt"))], "new")
        complete = FakeRun(
            [
                FakeFile(Path(name))
                for name in (*RUN_FILES, "model_9.pt", "model_100.pt")
            ]
        )
        api = FakeApi([incomplete, complete])
        path, _, checkpoint = select_run(api, None, None, "catbot", None)
        self.assertEqual((path, checkpoint), ("team/catbot/run1", "model_100.pt"))
        self.assertEqual(api.request, ("team/catbot", "-created_at"))
        self.assertIsNone(latest_checkpoint({"other.pt": None}))

    def test_explicit_run_rejects_missing_metadata(self):
        api = FakeApi([FakeRun([FakeFile(Path("model_1.pt"))])])
        with self.assertRaisesRegex(ValueError, "missing.*manifest.json"):
            select_run(api, "team/catbot/run1", None, "catbot", None)

    def test_explicit_checkpoint_is_retained(self):
        api = FakeApi(
            [
                FakeRun(
                    [
                        FakeFile(Path(name))
                        for name in (*RUN_FILES, "model_1.pt", "model_20.pt")
                    ]
                )
            ]
        )
        _, _, checkpoint = select_run(
            api, "team/catbot/run1", None, "catbot", "model_1.pt"
        )
        self.assertEqual(checkpoint, "model_1.pt")

    def test_invalid_arguments_do_not_reach_wandb(self):
        for arguments in (
            ["team/catbot/../run"],
            ["team/catbot/run", "../model_1.pt"],
            ["--project", "../catbot"],
        ):
            with (
                self.subTest(arguments=arguments),
                patch("sys.stderr"),
                self.assertRaises(SystemExit) as error,
            ):
                main(arguments)
            self.assertEqual(error.exception.code, 2)


@unittest.skipUnless(
    HAS_RSL, "Export checks require pull_policy.py's RSL-RL dependencies"
)
class DeploymentTests(unittest.TestCase):
    def setUp(self):
        from rsl_rl.models import MLPModel
        from tensordict import TensorDict

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.cache = self.root / "cache"
        make_bundle(self.source)
        metadata = json.loads((self.source / "policy.json").read_text())
        self.actor_config = {
            "class_name": "MLPModel",
            "hidden_dims": [32, 16],
            "activation": "elu",
            "obs_normalization": True,
            "distribution_cfg": {
                "class_name": "GaussianDistribution",
                "init_std": 0.5,
                "std_type": "scalar",
            },
        }
        options = copy.deepcopy(self.actor_config)
        options.pop("class_name")
        samples = (
            torch.randn(128, 90, generator=torch.Generator().manual_seed(7)) * 2 + 3
        )
        observations = TensorDict({"actor": samples}, batch_size=[128])
        self.actor = MLPModel(
            observations, {"actor": ["actor"]}, "actor", 12, **options
        )
        self.actor.train()
        self.actor.update_normalization(observations)
        self.actor.eval()
        self.checkpoint = self.source / "model_100.pt"
        torch.save(
            {"actor_state_dict": self.actor.state_dict(), "iter": 100, "infos": None},
            self.checkpoint,
        )
        xml = "<mujoco model='saved-training-model'/>"
        config = {
            "environment": metadata["settings"],
            "robot": {"saved": True},
            "runner": {"actor": self.actor_config, "obs_groups": {"actor": ["actor"]}},
        }
        self.manifest = {
            "schema_version": 1,
            **config,
            "model_sha256": hashlib.sha256(xml.encode()).hexdigest(),
            "policy_contract": metadata["policy_contract"],
            "dependency_versions": {"torch": torch.__version__, "rsl-rl-lib": "5.4.2"},
        }
        (self.source / "config.json").write_text(json.dumps(config))
        (self.source / "model.xml").write_text(xml)
        self.save_manifest()
        self.files = [
            FakeFile(self.source / name) for name in (*RUN_FILES, self.checkpoint.name)
        ]
        self.api = FakeApi([FakeRun(self.files)])

    def save_manifest(self):
        (self.source / "manifest.json").write_text(json.dumps(self.manifest))

    def prepare(self):
        return prepare_policy(self.api, directory=self.cache)

    def test_download_export_runtime_parity_with_learned_normalization(self):
        from tensordict import TensorDict

        bundle = self.prepare()
        runtime = PolicyRuntime(bundle)
        self.assertEqual((self.cache / "latest").resolve(), bundle)
        self.assertTrue((bundle.parent / self.checkpoint.name).is_file())
        inputs = torch.randn(1, 90) * 2 + 3
        with torch.inference_mode():
            expected = self.actor(TensorDict({"actor": inputs}, batch_size=[1]))
            torch.testing.assert_close(runtime.actor(inputs), expected)
            self.assertFalse(
                torch.allclose(runtime.actor(inputs), self.actor.mlp(inputs))
            )
        source = json.loads((bundle / "source.json").read_text())
        self.assertEqual(source["run"], "team/catbot/run1")
        self.assertEqual(source["checkpoint"], "model_100.pt")

    def test_repeat_refreshes_downloads_and_reuses_valid_bundle(self):
        first = self.prepare()
        with patch("catbot_policy.deployment.export_checkpoint") as export:
            self.assertEqual(self.prepare(), first)
            export.assert_not_called()
        self.assertTrue(all(file.downloads == 2 for file in self.files))

    def test_cli_prepares_bundle_and_prints_quoted_ros_command(self):
        directory = self.root / "cache with spaces"
        wandb = SimpleNamespace(Api=lambda: self.api, Error=RuntimeError)
        output = io.StringIO()
        with patch.dict(sys.modules, {"wandb": wandb}), patch("sys.stdout", output):
            main(["--directory", str(directory)])
        command = shlex.split(output.getvalue().splitlines()[-1])
        self.assertEqual(
            command[:4], ["ros2", "launch", "catbot_policy", "catbot.launch.py"]
        )
        self.assertEqual(
            command[4], f"policy_bundle:={(directory / 'latest').resolve()}"
        )

    def test_same_checkpoint_name_with_new_weights_selects_new_bundle(self):
        first = self.prepare()
        with torch.no_grad():
            next(self.actor.mlp.parameters()).add_(0.25)
        torch.save({"actor_state_dict": self.actor.state_dict()}, self.checkpoint)
        second = self.prepare()
        self.assertNotEqual(first, second)
        self.assertEqual((self.cache / "latest").resolve(), second)

    def test_failed_download_or_export_preserves_previous_selection(self):
        first = self.prepare()
        self.files[-1].fail = True
        with self.assertRaisesRegex(OSError, "Interrupted"):
            self.prepare()
        self.files[-1].fail = False
        self.manifest["policy_contract"]["version"] = 1
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Incompatible"):
            self.prepare()
        self.assertEqual((self.cache / "latest").resolve(), first)
        self.assertEqual(list(self.cache.glob(".download-*")), [])

    def test_bad_manifest_is_rejected_before_loading_weights(self):
        for change in ("model", "config", "version", "observations"):
            with self.subTest(change=change):
                manifest = copy.deepcopy(self.manifest)
                if change == "model":
                    self.manifest["model_sha256"] = "0" * 64
                elif change == "config":
                    self.manifest["robot"] = {"tampered": True}
                elif change == "version":
                    self.manifest["dependency_versions"]["torch"] = "1.0.0"
                else:
                    self.manifest["policy_contract"]["observations"].reverse()
                self.save_manifest()
                with patch("torch.load") as load, self.assertRaises(ValueError):
                    export_checkpoint(self.checkpoint, self.root / "bad-export")
                load.assert_not_called()
                self.manifest = manifest

    def test_corrupt_cached_actor_does_not_replace_selection(self):
        bundle = self.prepare()
        (bundle / "policy.pt").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.prepare()
        self.assertEqual((self.cache / "latest").resolve(), bundle)

    def test_unsupported_actor_is_rejected(self):
        config_path = self.source / "config.json"
        config = json.loads(config_path.read_text())
        config["runner"]["actor"]["class_name"] = "RNNModel"
        config_path.write_text(json.dumps(config))
        self.manifest["runner"] = config["runner"]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "MLPModel"):
            export_checkpoint(self.checkpoint, self.root / "unsupported")


if __name__ == "__main__":
    unittest.main()
