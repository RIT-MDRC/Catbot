"""Exported Foxglove layout contracts; SDK notebook layouts are not import files."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "foxglove"


def leaves(tree):
    if isinstance(tree, str):
        return [tree]
    assert tree["direction"] in ("row", "column")
    assert 0 < tree.get("splitPercentage", 50) < 100
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
    visited = set()
    for panel_id in ids:
        assert panel_id not in visited
        visited.add(panel_id)
        if panel_id.startswith("Tab!"):
            for tab in data["configById"][panel_id]["tabs"]:
                ids.extend(leaves(tab["layout"]))
    assert set(ids) == set(data["configById"])
    for key, config in data["configById"].items():
        kind = key.split("!")[0]
        assert kind in (
            "CallService",
            "RawMessages",
            "Plot",
            "3D",
            "TransformTree",
            "Tab",
            "catbot-tuning.actuator-positions",
            "catbot-tuning.actuator-tuning",
        )
        if kind == "CallService":
            assert config["serviceName"] == "/camera/calibration/start" or config[
                "serviceName"
            ].startswith(("/rpi/supervisor/", "/orin/supervisor/"))
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
    home = next(c for c in configs if c.get("buttonText") == "Home robot")
    assert home["serviceName"] == "/rpi/supervisor/script"
    assert json.loads(home["requestPayload"]) == {"name": "home_robot"}
