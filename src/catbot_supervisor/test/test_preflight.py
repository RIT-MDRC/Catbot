from types import SimpleNamespace

import pytest
from catbot_supervisor.preflight import ClockMonitor, compute_warning, verdict


@pytest.mark.parametrize("bound,warning,rejected", [(0.019, False, False), (0.02, True, False), (0.05, True, False), (0.051, False, True)])
def test_clock_status_warning_and_rejection(bound, warning, rejected):
    clock = ClockMonitor()
    clock.offset, clock.uncertainty, clock.received = bound, 0.0, 10.0
    clock.reason = ""
    status = clock.status(10.1)
    assert status["bound_seconds"] == pytest.approx(bound)
    assert status["warning"] is warning
    assert bool(status["reason"]) is rejected
    assert clock.status(13.0)["reason"] == "clock exchange stale"


@pytest.mark.parametrize("offset,passes", [(0.0, True), (0.05, False), (-0.05, False)])
def test_clock_exchange_bounds_skew_in_both_directions(offset, passes):
    clock = ClockMonitor()
    clock.sent(1, 100, 10)
    assert clock.reply(1, 100, 100.002 + offset, 100.003 + offset, 100.005, 10.005)
    assert clock.offset == pytest.approx(offset)
    assert clock.uncertainty == pytest.approx(0.002)
    assert bool(not clock.verdict(10.01)) == passes
    assert clock.verdict(13) == "clock exchange stale"
    assert not clock.reply(1, 100, 100, 100, 100, 10)


@pytest.mark.parametrize(
    "origin,rx,tx,end,now",
    [
        (99, 100, 100, 100.01, 10.01),
        (100, 101, 100, 100.01, 10.01),
        (100, 100, 100, 200, 10.01),
        (100, 100, 100, 100.5, 10.5),
    ],
)
def test_invalid_or_delayed_clock_exchange_cannot_pass(origin, rx, tx, end, now):
    clock = ClockMonitor()
    clock.sent(1, 100, 10)
    assert not clock.reply(1, origin, rx, tx, end, now)
    assert clock.verdict(now)


def test_preflight_rejects_temperature_disk_and_unknown():
    resources = {"errors": [], "temperature_c": 50, "disk_free_bytes": 100}
    compute = SimpleNamespace(available=True, reason="no CUDA")
    clock = ClockMonitor()
    clock.sent(1, 100, 10)
    clock.reply(1, 100, 100.001, 100.001, 100.002, 10.002)
    assert not verdict(resources, clock, compute, 10.01, 80, 10)
    assert verdict(None, clock, compute, 10.01, 80, 10)
    resources["temperature_c"] = 81
    assert "temperature" in verdict(resources, clock, compute, 10.01, 80, 10)
    resources["temperature_c"] = 50
    assert "disk" in verdict(resources, clock, compute, 10.01, 80, 101)
    compute.available = False
    assert not verdict(resources, clock, compute, 10.01, 80, 10)
    assert "CUDA" in compute_warning(resources, compute)
    resources["errors"] = ["cpu/memory: unavailable"]
    assert not verdict(resources, clock, compute, 10.01, 80, 10)
    assert "cpu/memory" in compute_warning(resources, compute)
    resources["errors"] = ["disk: unavailable"]
    assert "disk" in verdict(resources, clock, compute, 10.01, 80, 10)


@pytest.mark.parametrize(
    "running,error,ready,action_at,reason",
    [
        (False, "", False, None, ""),
        (False, "job exited (1)", False, None, "job exited"),
        (True, "", False, None, "not ready"),
        (True, "", True, None, "stream unavailable"),
        (True, "", True, 9.0, "stream unavailable"),
        (True, "", True, 10.0, ""),
    ],
)
def test_policy_standby_is_healthy_but_failures_are_not(
    running, error, ready, action_at, reason
):
    from catbot_supervisor.preflight import policy_fault

    result = policy_fault(
        running=running,
        error=error,
        ready=ready,
        action_at=action_at,
        now=10.1,
        timeout=0.25,
    )
    assert (reason in result) if reason else result == ""


@pytest.mark.parametrize(
    "received,now,state",
    [(None, 10, "waiting"), (9, 10, "lost"), (11, 10, "lost"), (9.9, 10, "connected")],
)
def test_pi_absence_has_actionable_reason_and_recovery(received, now, state):
    from catbot_supervisor.preflight import pi_link_status

    status = pi_link_status(received, now, 0.5)
    assert status["state"] == state
    assert status["available"] == (state == "connected")
    if state != "connected":
        assert "Pi unavailable" in status["reason"]
        assert "powered off" in status["reason"]
        assert "motion remain blocked" in status["reason"]
    else:
        assert status["reason"] == ""
