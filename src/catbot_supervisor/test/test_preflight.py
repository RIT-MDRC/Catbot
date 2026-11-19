from types import SimpleNamespace

import pytest
from catbot_supervisor.preflight import ClockMonitor, verdict


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


def test_preflight_rejects_temperature_disk_device_and_unknown():
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
    assert "CUDA" in verdict(resources, clock, compute, 10.01, 80, 10)
