from types import SimpleNamespace

import pytest
from catbot_supervisor.homing import ERROR_FIELDS, StateCycle, at_position, fault_reason
from catbot_supervisor.scripts import calibrate_robot, home_robot, registry

NAMES = tuple(
    f"{leg}{joint}" for leg in ("fl", "fr", "bl", "br") for joint in ("a", "f", "k")
)


def healthy():
    return {
        n: SimpleNamespace(
            heartbeat_available=True, axis_state=1, **dict.fromkeys(ERROR_FIELDS, 0)
        )
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


@pytest.mark.parametrize(
    "state,active", [(3, 4), (3, 6), (3, 7), (3, 12), (3, 13), (11, 11)]
)
def test_parallel_cycle_tracks_each_axis_even_when_active_windows_do_not_overlap(
    state, active
):
    body = healthy()
    names = ("flk", "frk")
    cycle = StateCycle(names, state)
    assert not cycle.complete(body)  # Initial IDLE is not completion.
    body["flk"].axis_state = active
    cycle.observe(body)
    body["flk"].axis_state = 1
    assert not cycle.complete(body)  # frk has never begun.
    body["frk"].axis_state = active
    assert not cycle.complete(body)
    body["frk"].axis_state = 1
    assert cycle.complete(body)


@pytest.mark.parametrize("field", ERROR_FIELDS)
def test_parallel_cycle_does_not_accept_faulted_idle_axis(field):
    body = healthy()
    cycle = StateCycle(("flk", "frk"), 11)
    for name in cycle.names:
        body[name].axis_state = 11
    cycle.observe(body)
    for name in cycle.names:
        body[name].axis_state = 1
    setattr(body["frk"], field, 8)
    with pytest.raises(RuntimeError, match="frk"):
        cycle.complete(body)


@pytest.mark.parametrize("missing", ["axis", "heartbeat"])
def test_parallel_cycle_requires_every_axis_heartbeat(missing):
    body = healthy()
    if missing == "axis":
        del body["frk"]
    else:
        body["frk"].heartbeat_available = False
    with pytest.raises(RuntimeError):
        StateCycle(("flk", "frk"), 3).complete(body)


def test_robot_calibration_batches_full_calibration_and_orders_homing_with_group_barriers():
    steps = registry()["calibrate"](NAMES)
    assert registry()["full_calibrate"](NAMES) == steps
    assert [
        (s.names, s.state) for s in steps if s.kind == "motor" and s.state == 3
    ] == [(NAMES, 3)]
    groups = [
        ("flk", "frk", "blk", "brk"),
        ("flf", "frf", "blf", "brf"),
        ("bla", "bra"),
        ("fla", "fra"),
    ]
    assert [s.names for s in steps if s.kind == "motor" and s.state == 11] == groups
    for group in groups:
        start = next(
            i
            for i, s in enumerate(steps)
            if s.kind == "motor" and s.state == 11 and s.names == group
        )
        assert steps[start + 1].kind == "wait_cycle" and steps[start + 1].names == group
        for name in group:
            arm = next(
                i
                for i, s in enumerate(steps)
                if s.kind == "motor" and s.state == 8 and s.names == (name,)
            )
            assert arm > start + 1
    move = next(i for i, s in enumerate(steps) if s.kind == "position")
    assert steps[move].names == ("flf", "frf") and steps[move].positions == (30.0, 30.0)
    assert [s.kind for s in steps[move : move + 4]] == [
        "position",
        "wait_position",
        "wait_operator",
        "motor",
    ]
    assert steps[move + 3].names == ("fla", "fra")
    assert not any(s.kind.startswith("job_") for s in steps)
    for names in (NAMES[:-1], (*NAMES, "extra"), (*NAMES, NAMES[0])):
        with pytest.raises(ValueError):
            calibrate_robot(names)


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
