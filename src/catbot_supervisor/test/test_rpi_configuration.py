"""Operational overrides change real script deadlines and keep hardware data separate."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from catbot_supervisor.homing import at_position
from catbot_supervisor.rpi_configuration import OperationalSettings
from catbot_supervisor.scripts import ScriptRunner, registry
from foundation.protocol import PROTOCOL_FILE, load_protocol

NAMES = tuple(
    leg + joint for leg in ("fl", "fr", "bl", "br") for joint in ("a", "f", "k")
)


def test_clear_timeout_override_changes_when_script_fails():
    settings = OperationalSettings(clear_errors_timeout_seconds=0.8)
    steps = registry(settings)["clear_errors"](NAMES)
    step = next(step for step in steps if step.kind == "wait_clear")
    runner = ScriptRunner(lambda _: None, lambda _: False)
    runner.start([step])
    runner.tick(1.0)
    runner.tick(1.79)
    assert not runner.error
    runner.tick(1.81)
    assert "wait_clear" in runner.error


def test_homing_overrides_clearance_delay_and_completion_budget():
    settings = OperationalSettings(
        front_flexion_clearance_degrees=12,
        homing_timeout_seconds=47,
        homing_delay_seconds=2,
        position_move_timeout_seconds=9,
    )
    steps = registry(settings)["home_robot"](NAMES)
    assert any(step.positions == (12, 12) for step in steps)
    assert all(step.timeout == 2 for step in steps if step.kind == "delay")
    assert all(step.timeout == 9 for step in steps if step.kind == "wait_position")
    assert all(step.timeout == 47 for step in steps if step.kind == "wait_cycle")


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True])
def test_invalid_operational_setting_rejected(value):
    with pytest.raises(ValueError, match="recovery_timeout_seconds"):
        replace(OperationalSettings(), recovery_timeout_seconds=value)


def test_configurable_settle_tolerances():
    body = {
        "a": SimpleNamespace(
            valid=True, position_degrees=0.7, velocity_degrees_per_second=0.6
        )
    }
    assert at_position(body, ["a"], [0], position_tolerance=1, velocity_tolerance=1)
    assert not at_position(
        body, ["a"], [0], position_tolerance=0.5, velocity_tolerance=1
    )
    assert not at_position(
        body, ["a"], [0], position_tolerance=1, velocity_tolerance=0.5
    )


def test_protocol_override_resolves_dbc_relative_to_selected_file(tmp_path):
    data = json.loads(PROTOCOL_FILE.read_text())
    data["dbc_file"] = str(PROTOCOL_FILE.parent / data["dbc_file"])
    data["MotorState"]["HOMING"] = 42
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(data))
    assert load_protocol(path)["MotorState"]["HOMING"] == 42
    data["MotorState"]["IDLE"] = 42
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="duplicate"):
        load_protocol(path)
