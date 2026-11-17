"""Local selection cases; no ROS, Torch, W&B or hardware required."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catbot_policy.artifacts import (
    DEFAULT_ENTITY,
    checkpoint_name,
    resolve_downloaded,
    run_path,
)


class ArtifactTests(unittest.TestCase):
    def test_defaults_and_numeric_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)

            def model(number, suffix="a"):
                root = (
                    cache
                    / DEFAULT_ENTITY
                    / "catbot"
                    / "ow4nsasy"
                    / f"model_{number}-{suffix}"
                )
                (root / "bundle").mkdir(parents=True)
                for name in (
                    "config.json",
                    "model.xml",
                    "manifest.json",
                    "bundle/policy.pt",
                    "bundle/policy.json",
                ):
                    (root / name).touch()
                (root / "bundle/source.json").write_text(
                    json.dumps(
                        {
                            "run": f"{DEFAULT_ENTITY}/catbot/ow4nsasy",
                            "checkpoint": f"model_{number}.pt",
                        }
                    )
                )
                return root

            older = model(9)
            newer = model(19999)
            (cache / "selected").symlink_to(older, target_is_directory=True)
            self.assertEqual(resolve_downloaded(cache), older)
            self.assertEqual(resolve_downloaded(cache, "ow4nsasy"), newer)
            self.assertEqual(resolve_downloaded(cache, "ow4nsasy", "9"), older)
            self.assertEqual(
                resolve_downloaded(
                    cache, f"{DEFAULT_ENTITY}/catbot/ow4nsasy", "model_9.pt"
                ),
                older,
            )
            for run, checkpoint in (
                ("missing", ""),
                ("ow4nsasy", "42"),
                ("../escape", ""),
                ("", "9"),
            ):
                with (
                    self.subTest(run=run, checkpoint=checkpoint),
                    self.assertRaisesRegex(ValueError, "Downloaded models:"),
                ):
                    resolve_downloaded(cache, run, checkpoint)
            model(19999, "b")
            with self.assertRaisesRegex(ValueError, "Multiple exports match"):
                resolve_downloaded(cache, "ow4nsasy")

    def test_downloader_shorthand(self):
        self.assertEqual(run_path("ow4nsasy"), f"{DEFAULT_ENTITY}/catbot/ow4nsasy")
        self.assertEqual(checkpoint_name("19999"), "model_19999.pt")
        self.assertEqual(checkpoint_name("model_19999.pt"), "model_19999.pt")
        for value in ("-1", "../../model_1.pt", "1.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checkpoint_name(value)
