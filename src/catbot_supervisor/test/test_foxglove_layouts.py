"""Exported Foxglove layout contracts; SDK notebook layouts are not import files."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "foxglove"


def leaves(tree):
    if isinstance(tree, str):
        return [tree]
    assert tree["direction"] in ("row", "column")
    assert 0 < tree["splitPercentage"] < 100
    return leaves(tree["first"]) + leaves(tree["second"])


@pytest.mark.parametrize("filename", ["main-dashboard.json", "software-estop.json"])
def test_layout_import_uses_exported_mosaic_and_registered_panel_ids(filename):
    data = json.loads((ROOT / filename).read_text())
    assert {
        "configById",
        "layout",
        "globalVariables",
        "userNodes",
        "playbackConfig",
    } <= data.keys()
    ids = leaves(data["layout"])
    assert len(ids) == len(set(ids))
    assert set(ids) == set(data["configById"])
    for key, config in data["configById"].items():
        kind = key.split("!")[0]
        assert kind in ("CallService", "RawMessages")
        if kind == "CallService":
            assert config["serviceName"].startswith(
                ("/rpi/supervisor/", "/orin/supervisor/")
            )
            assert isinstance(json.loads(config["requestPayload"]), dict)


def test_policy_start_and_script_execution_are_independent_controls():
    configs = json.loads((ROOT / "main-dashboard.json").read_text())[
        "configById"
    ].values()
    start = next(
        c for c in configs if c.get("buttonText") == "Start policy (no motor commands)"
    )
    assert start["serviceName"] == "/orin/supervisor/job"
    assert json.loads(start["requestPayload"]) == {
        "name": "policy",
        "operation": "start",
    }
    script = next(c for c in configs if c.get("buttonText") == "Run named script")
    assert script["serviceName"] == "/rpi/supervisor/script" and script["editingMode"]
