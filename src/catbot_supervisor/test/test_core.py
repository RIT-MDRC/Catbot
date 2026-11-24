"""Adversarial link decisions without ROS, clocks, or hardware."""

import math

import pytest
from catbot_supervisor.core import (
    ActionGate,
    Limits,
    Mode,
    status_bool,
    status_float,
    status_sequence,
    status_string,
    status_uint32,
    status_uint64,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), (-1, 0), (0, 0), (1.9, 1), ("7", 7), ("bad", 0)],
)
def test_status_sequence_normalizes_unsigned_values(value, expected):
    result = status_sequence(value)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), (-1, 0), (0, 0), (12, 12), (0x100000000, 0xFFFFFFFF)],
)
def test_status_uint32_normalizes_values(value, expected):
    result = status_uint32(value)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), (-1, 0), (0, 0), (12, 12), ("42", 42)],
)
def test_status_uint64_normalizes_values(value, expected):
    result = status_uint64(value)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0.0), (float("nan"), 0.0), (float("inf"), 0.0), (3, 3.0)],
)
def test_status_float_normalizes_values(value, expected):
    result = status_float(value)
    assert type(result) is float
    assert result == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, ""), (False, "False"), (7, "7"), ("ready", "ready")],
)
def test_status_string_normalizes_values(value, expected):
    result = status_string(value)
    assert type(result) is str
    assert result == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), (0, False), (1, True), ("", False), ("false", True)],
)
def test_status_bool_normalizes_values(value, expected):
    result = status_bool(value)
    assert type(result) is bool
    assert result is expected


def healthy(mode=Mode.READY):
    gate = ActionGate(
        Limits(
            action_age=0.25,
            heartbeat_age=0.5,
            max_rtt=0.15,
            max_jitter=0.05,
            future_tolerance=0.02,
        )
    )
    probe = gate.probe(10.0)
    assert gate.heartbeat("session", 1, False, probe, 10.01)
    gate.mode = mode
    return gate


def action(gate, **changes):
    values = {
        "session": "session",
        "sequence": 1,
        "stamp": 100.0,
        "wall_now": 100.01,
        "now": 10.02,
        "names": ["flk"],
        "positions": [1.0],
    }
    values.update(changes)
    return gate.action(**values)


def test_gate_tracks_actions_in_ready_but_only_forwards_running():
    gate = healthy()
    assert not action(gate)
    gate.start(10.03)
    assert action(gate, sequence=2, stamp=100.02)
    assert gate.mode == Mode.RUNNING


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"session": "other"}, "session"),
        ({"stamp": 99.0}, "stale"),
        ({"stamp": 101.0}, "clocks"),
        ({"stamp": math.nan}, "stale"),
        ({"stamp": math.inf}, "stale"),
        ({"names": []}, "malformed"),
        ({"names": ["flk", "flk"], "positions": [1.0, 2.0]}, "malformed"),
        ({"positions": [math.nan]}, "malformed"),
        ({"positions": [math.inf]}, "malformed"),
    ],
)
def test_bad_actions_degrade_and_never_forward(changes, reason):
    gate = healthy(Mode.RUNNING)
    assert not action(gate, **changes)
    assert gate.mode == Mode.DEGRADED
    assert reason in gate.reason


@pytest.mark.parametrize("sequence", [0, 1, 3, 100])
def test_duplicate_reordered_or_gapped_actions_fail(sequence):
    gate = healthy(Mode.RUNNING)
    assert action(gate)
    assert not action(gate, sequence=sequence)
    assert gate.mode == Mode.DEGRADED


@pytest.mark.parametrize("mode", [Mode.BOOT, Mode.IDLE])
def test_closed_gate_resynchronizes_forward_gaps_without_forwarding(mode):
    gate = healthy(mode)
    assert not action(gate, sequence=1)
    assert gate.action_sequence == 1
    assert not action(gate, sequence=4, stamp=99.0)
    assert gate.action_sequence == 1
    assert not action(gate, sequence=4, stamp=100.02)
    assert gate.action_sequence == 4
    assert not action(gate, sequence=4, stamp=100.03)
    assert gate.action_sequence == 4
    assert not action(gate, sequence=3, stamp=100.03)
    assert gate.action_sequence == 4
    assert not action(gate, sequence=5, stamp=100.03)
    assert gate.action_sequence == 5


@pytest.mark.parametrize(
    "changes",
    [
        {"session": "other"},
        {"stamp": 99.0},
        {"stamp": 101.0},
        {"stamp": math.nan},
        {"names": []},
        {"positions": [math.nan]},
    ],
)
def test_idle_gap_cannot_bypass_action_validation(changes):
    gate = healthy(Mode.IDLE)
    action(gate, sequence=1)
    assert not action(gate, sequence=4, **changes)
    assert gate.action_sequence == 1
    assert gate.action_at == 10.02
    assert not action(gate, sequence=4, stamp=100.02)
    assert gate.action_sequence == 4


@pytest.mark.parametrize("mode", [Mode.READY, Mode.HOLDING, Mode.RUNNING])
def test_open_or_armed_gate_never_resynchronizes_a_gap(mode):
    gate = healthy(mode)
    action(gate, sequence=1)
    assert not action(gate, sequence=3, stamp=100.02)
    assert gate.action_sequence == 1
    assert gate.mode == (Mode.DEGRADED if mode != Mode.HOLDING else Mode.HOLDING)
    with pytest.raises(ValueError):
        gate.start(10.03)


def test_timestamp_regression_even_if_age_is_fresh():
    gate = healthy(Mode.RUNNING)
    assert action(gate)
    assert not action(gate, sequence=2, stamp=99.99)
    assert "regressed" in gate.reason


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("heartbeat", "heartbeat lost"),
        ("actions", "action stream stale"),
        ("probe", "probe echo lost"),
        ("degraded", "reported degraded"),
        ("rtt", "RTT or jitter"),
        ("jitter", "RTT or jitter"),
    ],
)
def test_link_faults_close_running_gate(fault, reason):
    gate = healthy(Mode.RUNNING)
    assert action(gate)
    now = 10.03
    if fault == "heartbeat":
        gate.heartbeat_at = 9.0
    elif fault == "actions":
        now, gate.heartbeat_at, gate.probe_at = 10.4, 10.4, 10.4
    elif fault == "probe":
        gate.probe_at = 9.0
    elif fault == "degraded":
        gate.orin_degraded = True
    elif fault == "rtt":
        gate.rtt = 0.2
    else:
        gate.jitter = 0.1
    assert not gate.check(now)
    assert gate.mode == Mode.DEGRADED
    assert reason in gate.reason


def test_probe_echoes_are_consumed_once_and_expire():
    gate = healthy()
    rtt = gate.rtt
    assert gate.heartbeat("session", 2, False, 1, 10.02)
    assert gate.rtt == rtt
    old = gate.probe(10.03)
    gate.probe(11.0)
    assert old not in gate.probes
    gate.heartbeat("session", 3, False, old, 11.01)
    assert "probe" in gate.reason


def test_rtt_jitter_is_measured_from_pi_round_trips():
    gate = healthy()
    probe = gate.probe(10.1)
    assert gate.heartbeat("session", 2, False, probe, 10.15)
    assert gate.rtt == pytest.approx(0.05)
    assert gate.jitter == pytest.approx(0.008)


@pytest.mark.parametrize("sequence", [0, 1])
def test_replayed_heartbeat_does_not_refresh_lease(sequence):
    gate = healthy()
    before = gate.heartbeat_at
    # Stay within the link's time limits so a missing replay check cannot pass
    # this test by tripping an unrelated timeout.
    assert not gate.heartbeat("session", sequence, False, 0, 10.03)
    assert gate.heartbeat_at == before
    assert gate.mode == Mode.DEGRADED


def test_session_restart_latches_until_explicit_recovery():
    gate = healthy(Mode.RUNNING)
    assert not gate.heartbeat("new", 1, False, 0, 10.02)
    gate.emergency(gate.reason)
    latched_reason = gate.reason
    assert not action(gate)
    gate.heartbeat("session", 2, False, 0, 10.03)
    assert gate.mode == Mode.EMERGENCY
    assert gate.reason == latched_reason
    gate.recover()
    assert gate.mode == Mode.IDLE
    probe = gate.probe(11.0)
    assert gate.heartbeat("new", 1, False, probe, 11.01)
    assert gate.session == "new"


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf])
def test_invalid_limits_fail_closed(value):
    with pytest.raises(ValueError):
        Limits(action_age=value)


def test_running_requires_ready_and_fresh_action():
    gate = healthy(Mode.IDLE)
    with pytest.raises(ValueError):
        gate.start(10.02)
    gate.mode = Mode.READY
    with pytest.raises(ValueError, match="stale"):
        gate.start(10.02)


def test_local_holding_requires_explicit_run_and_fresh_policy():
    gate = healthy(Mode.HOLDING)
    with pytest.raises(ValueError, match="Orin action stream stale"):
        gate.start(10.02)
    assert not action(gate)
    assert gate.mode == Mode.HOLDING
    gate.start(10.03)
    assert gate.mode == Mode.RUNNING


def test_idle_or_degraded_orin_does_not_interrupt_local_hold():
    gate = healthy(Mode.HOLDING)
    # Missing/degraded Orin is irrelevant to local holding; never enters RUNNING.
    gate.heartbeat("session", 2, True, 0, 10.03)
    assert gate.mode == Mode.HOLDING


def test_delayed_queue_never_refreshes_action_watchdog():
    from catbot_supervisor.core import ActionGate, Mode

    gate = ActionGate()
    gate.mode = Mode.RUNNING
    gate.session = "session"
    gate.heartbeat_at = gate.probe_at = 10.0
    gate.orin_degraded = False
    gate.rtt = 0.001
    gate.action_at = 9.99
    # DDS delivers a previously queued action while monotonic link health is fresh.
    assert not gate.action("session", 1, 100.0, 100.4, 10.0, ["motor"], [0.0])
    assert gate.action_at == 9.99
    assert gate.mode == Mode.DEGRADED
    # Later queued messages cannot reopen a fail-latched gate.
    assert not gate.action("session", 2, 100.4, 100.4, 10.01, ["motor"], [1.0])
    assert gate.action_at == 9.99


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"heartbeat_at": None}, "Orin heartbeat lost"),
        ({"orin_degraded": True}, "Orin reported degraded"),
        ({"probe_at": None}, "Orin probe echo lost"),
        ({"rtt": None}, "Orin RTT or jitter exceeds limit"),
        ({"action_at": None}, "Orin action stream stale"),
    ],
)
def test_holding_run_reports_the_actual_link_failure(changes, expected):
    gate = healthy(Mode.HOLDING)
    gate.action_at = 10.01
    for name, value in changes.items():
        setattr(gate, name, value)
    with pytest.raises(ValueError, match=expected):
        gate.start(10.02)
    assert gate.mode == Mode.HOLDING
