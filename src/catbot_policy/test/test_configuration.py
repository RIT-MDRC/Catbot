"""Shared configuration checks that run without ROS or CUDA."""

import copy
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mapping_fixture import mapping_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catbot_policy.configuration import validate_mapping
from catbot_policy.files import sha256_file
from catbot_policy.worker_launch import WorkerLaunchSpec


class ConfigurationTests(unittest.TestCase):
    def test_worker_resolution_and_environment_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            environment = project / ".venv-cuda"
            with self.assertRaisesRegex(ValueError, "Prepare"):
                WorkerLaunchSpec.build(
                    project,
                    "uv",
                    ["worker.py"],
                    device="cuda:0",
                    environment="auto",
                    sync="auto",
                )
            (environment / "bin").mkdir(parents=True)
            (environment / "bin/python").touch()
            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": "ros",
                    "PYTHONHOME": "ros",
                    "VIRTUAL_ENV": "ros",
                    "UV_PROJECT_ENVIRONMENT": "wrong",
                    "PATH": "keep",
                },
            ):
                spec = WorkerLaunchSpec.build(
                    project,
                    "uv",
                    ["worker.py"],
                    device="cuda:0",
                    environment="auto",
                    sync="auto",
                    python="3.14",
                )
            self.assertEqual(
                spec.command,
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "--project",
                    str(project),
                    "--python",
                    "3.14",
                    "python",
                    "worker.py",
                    "--device",
                    "cuda:0",
                ],
            )
            self.assertEqual(
                spec.environment["UV_PROJECT_ENVIRONMENT"], str(environment)
            )
            self.assertEqual(spec.environment["PATH"], "keep")
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
                self.assertNotIn(key, spec.environment)
            self.assertEqual(
                WorkerLaunchSpec.resolve("cpu", project, "auto", "auto"), ("", True)
            )
            self.assertEqual(
                WorkerLaunchSpec.resolve("cuda", project, "", "true"), ("", True)
            )
            with self.assertRaises(ValueError):
                WorkerLaunchSpec.resolve("cpu", project, "", "invalid")

    def test_mapping_rejections(self):
        mapping = mapping_values()
        validate_mapping(mapping)
        for key, value in [
            ("actuator_names", ["a"] * 12),
            ("signs", [0] * 12),
            ("offsets_degrees", [float("nan")] * 12),
            ("minimum_degrees", mapping["maximum_degrees"]),
            ("maximum_degrees", [0] * 11),
        ]:
            invalid = copy.deepcopy(mapping)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_mapping(invalid)

    def test_streaming_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data"
            for data in (b"", b"catbot" * 400000):
                path.write_bytes(data)
                self.assertEqual(sha256_file(path), hashlib.sha256(data).hexdigest())
