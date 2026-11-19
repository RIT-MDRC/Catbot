"""Adversarial link decisions without ROS, clocks, or hardware."""

import math

import pytest
from catbot_supervisor.core import ActionGate, Limits, Mode


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
