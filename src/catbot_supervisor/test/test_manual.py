import pytest
from catbot_supervisor.manual import ManualControl


def request(gate, seq=1, **kwargs):
    values = {
        "client": "client",
        "sequence": seq,
        "axis": "flk",
        "position": 10.0,
        "minimum": -55.0,
        "maximum": 55.0,
        "now": 1.0,
        "streaming": True,
    }
    values.update(kwargs)
    gate.accept(**values)


def test_manual_stream_order_settle_and_timeout():
    gate = ManualControl()
    request(gate)
    with pytest.raises(ValueError, match="order"):
        request(gate)
    request(gate, 2, position=11.0, now=1.1)
    assert gate.tick(1.2, {"flk": (True, 11.0, 0.0)}) == []
    assert gate.active()
    gate.tick(1.7, {"flk": (True, 11.0, 0.0)})
    assert not gate.active()
    request(gate, 3, now=2.0, streaming=False)
    assert gate.tick(17.0, {}) == ["flk"]
    assert not gate.active()


def test_manual_rejects_outside_limits_and_supports_independent_clients_and_axes():
    gate = ManualControl()
    with pytest.raises(ValueError, match="limits"):
        request(gate, position=56.0)
    request(gate)
    request(gate, client="second", position=-10.0)
    request(gate, axis="fra")
    assert gate.targets["flk"].position == -10.0
    assert gate.targets["fra"].position == 10.0
