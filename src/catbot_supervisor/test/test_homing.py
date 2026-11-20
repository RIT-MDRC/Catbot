from types import SimpleNamespace

import pytest
from catbot_supervisor.homing import ERROR_FIELDS, at_position, fault_reason
from catbot_supervisor.scripts import home_robot

NAMES = tuple(
    f"{leg}{joint}" for leg in ("fl", "fr", "bl", "br") for joint in ("a", "f", "k")
)


def healthy():
    return {
        n: SimpleNamespace(heartbeat_available=True, **dict.fromkeys(ERROR_FIELDS, 0))
        for n in NAMES
    }


@pytest.mark.parametrize("field", ERROR_FIELDS)
@pytest.mark.parametrize("name", NAMES)
def test_any_fault_on_any_axis_blocks_homing(field, name):
    body = healthy()
    assert fault_reason(body, NAMES) == ""
    setattr(body[name], field, 8)
    assert name in fault_reason(body, NAMES)
    assert field in fault_reason(body, NAMES)


def test_missing_axis_or_heartbeat_blocks_homing():
    body = healthy()
    body["flk"].heartbeat_available = False
    assert "flk" in fault_reason(body, NAMES)
    del body["flk"]
    assert fault_reason(body, NAMES)


def test_homing_stages_hold_each_axis_and_gate_abduction_on_operator():
    steps = home_robot(NAMES)
    homed = [s.names[0] for s in steps if s.kind == "motor" and s.state == 11]
    assert homed == [
        "flk",
        "frk",
        "blk",
        "brk",
        "flf",
        "frf",
        "blf",
        "brf",
        "fla",
        "fra",
        "bla",
        "bra",
    ]
    assert not any(s.operation == "clear_errors" for s in steps)
    for name in NAMES:
        start = next(
            i for i, s in enumerate(steps) if s.state == 11 and s.names == (name,)
        )
        assert [(s.kind, s.operation, s.state) for s in steps[start : start + 7]] == [
            ("motor", "state", 11),
            ("wait_state", "", 11),
            ("wait_state", "", 1),
            ("motor", "trajectory", 0),
            ("motor", "hold", 0),
            ("motor", "state", 8),
            ("wait_ready", "", 0),
        ]
    move = next(i for i, s in enumerate(steps) if s.kind == "position")
    assert steps[move].names == ("flf", "frf")
    assert steps[move].positions == (30.0, 30.0)
    assert [s.kind for s in steps[move : move + 6]] == [
        "position",
        "wait_position",
        "delay",
        "wait_operator",
        "delay",
        "motor",
    ]
    assert steps[move + 5].names == ("fla",)
    assert [s.timeout for s in steps if s.kind == "delay"] == [15.0] * 5
    for name in ("brk", "brf", "bra"):
        ready = next(
            i
            for i, s in enumerate(steps)
            if s.kind == "wait_ready" and s.names == (name,)
        )
        assert steps[ready + 1].kind == "delay"
    with pytest.raises(ValueError):
        home_robot(NAMES[:-1])


@pytest.mark.parametrize(
    "position,velocity,valid,expected",
    [
        (30.0, 0.0, True, True),
        (27.0, 0.0, True, False),
        (30.0, 2.0, True, False),
        (30.0, 0.0, False, False),
        (float("nan"), 0.0, True, False),
        (30.0, float("inf"), True, False),
    ],
)
def test_position_wait_requires_valid_settled_measured_feedback(
    position, velocity, valid, expected
):
    body = {
        "flf": SimpleNamespace(
            position_degrees=position, velocity_degrees_per_second=velocity, valid=valid
        )
    }
    assert at_position(body, ("flf",), (30.0,)) == expected
    assert not at_position(body, ("flf", "frf"), (30.0, 30.0))
