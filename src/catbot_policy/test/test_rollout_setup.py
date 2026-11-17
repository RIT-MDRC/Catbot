"""Simulator setup must not sync the caller's CUDA environment."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catbot_policy.rollout_setup import find_rollout_repository, prepare_rollout


class RolloutSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repository = self.root / "external/catbot_sim_rollout"
        worker = self.repository / "src/catbot_rollout/worker.py"
        worker.parent.mkdir(parents=True)
        worker.touch()
        self.project = self.repository / "pyproject.toml"
        self.project.write_text(
            '[tool.uv.sources]\ncatbot-mujoco = { git = "ssh://example/repo", rev = "'
            + "a" * 40
            + '" }\n'
        )
        self.lock = self.repository / "uv.lock"
        self.lock.write_text("original lock")
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"git_revision": "b" * 40}))

    def test_workspace_discovery_and_isolated_environment(self):
        with patch("pathlib.Path.cwd", return_value=self.root):
            self.assertEqual(find_rollout_repository(), self.repository)
        with (
            patch.dict(
                os.environ,
                {
                    "UV_PROJECT_ENVIRONMENT": "/gpu/.venv-cuda",
                    "VIRTUAL_ENV": "/gpu/.venv-cuda",
                    "PYTHONPATH": "/ros",
                },
            ),
            patch("catbot_policy.rollout_setup.subprocess.run") as run,
        ):
            prepare_rollout(self.repository, self.root)
        self.assertIn("b" * 40, self.project.read_text())
        self.assertEqual(run.call_count, 3)
        for call in run.call_args_list:
            env = call.kwargs["env"]
            self.assertEqual(
                env["UV_PROJECT_ENVIRONMENT"], str(self.repository / ".venv")
            )
            self.assertNotIn("VIRTUAL_ENV", env)
            self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(
            run.call_args.args[0][0], str(self.repository / ".venv/bin/python")
        )

    def test_failures_restore_dependency_files(self):
        for failed_step in range(3):
            with self.subTest(failed_step=failed_step):
                project = self.project.read_bytes()

                def execute(*args, failed_step=failed_step, **kwargs):
                    self.lock.write_text("changed lock")
                    execute.calls += 1
                    if execute.calls == failed_step + 1:
                        raise subprocess.CalledProcessError(1, args[0])

                execute.calls = 0
                with (
                    patch(
                        "catbot_policy.rollout_setup.subprocess.run",
                        side_effect=execute,
                    ),
                    self.assertRaisesRegex(RuntimeError, "policy selection unchanged"),
                ):
                    prepare_rollout(self.repository, self.root)
                self.assertEqual(self.project.read_bytes(), project)
                self.assertEqual(self.lock.read_text(), "original lock")

    def test_invalid_revision_never_runs_uv(self):
        self.manifest.write_text(json.dumps({"git_revision": "main"}))
        with patch("catbot_policy.rollout_setup.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "full git_revision"):
                prepare_rollout(self.repository, self.root)
            run.assert_not_called()
