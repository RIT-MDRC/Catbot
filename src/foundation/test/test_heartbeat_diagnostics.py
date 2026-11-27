import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "foundation"))
from component.can.can_bus import CanBus, get_receive_health, read_message
from heartbeat_diagnostics import HeartbeatDiagnostics


def feedback(available=True):
    flags = {}
    for field in ("axis", "motor", "encoder", "sensorless", "controller"):
        flags[field + "_error_flags"] = 0
        flags[field + "_error_messages"] = []
    axis = NS(
        actuator_name="fra",
        axis_id=7,
        axis_state=8,
        ready=available,
        heartbeat_available=available,
        **flags,
    )
    return NS(actuators=[axis]), {
        "fra": NS(last_heartbeat_time=0, last_encoder_estimate_time=0)
    }


def test_event_logging_is_rate_limited_and_periodic_without_new_receivers(tmp_path):
    path = tmp_path / "heartbeat.jsonl"
    journal = HeartbeatDiagnostics(
        path, lambda: {"existing_bus": {"frames_processed": 12}}, host=dict
    )
    message, motors = feedback()
    try:
        journal.observe(message, motors, 0)
        message.actuators[0].heartbeat_available = False
        journal.observe(message, motors, 0.1)
        journal.observe(message, motors, 0.5)
        journal.observe(message, motors, 1)
        message.actuators[0].heartbeat_available = True
        journal.observe(message, motors, 1.1)
        journal.observe(message, motors, 2)
        journal.observe(message, motors, 7)
        journal.queue.join()
    finally:
        journal.close()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["event"] for r in records] == [
        "startup",
        "heartbeat_change",
        "heartbeat_change",
        "periodic",
    ]
    assert records[1]["changes"] == {"fra:lost": 1}
    assert records[2]["changes"] == {"fra:restored": 1}
    assert records[1]["axes"][0]["heartbeat_age_ms"] == 1000
    assert records[1]["receive"]["existing_bus"]["frames_processed"] == 12


def test_full_queue_drops_diagnostics_without_blocking_feedback(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def receive_health():
        entered.set()
        release.wait(timeout=2)
        return {}

    journal = HeartbeatDiagnostics(
        tmp_path / "log", receive_health, host=dict, queue_size=1
    )
    message, motors = feedback()
    try:
        journal.observe(message, motors, 0)
        assert entered.wait(timeout=1)
        journal.observe(message, motors, 5)
        journal.observe(message, motors, 10)
        assert journal.dropped == 1
    finally:
        release.set()
        journal.close()


def test_logs_rotate_and_keep_only_three_bounded_segments(tmp_path):
    path = tmp_path / "log"
    journal = HeartbeatDiagnostics(path, dict, host=dict, max_bytes=1)
    message, motors = feedback()
    try:
        for now in (0, 5, 10, 15):
            journal.observe(message, motors, now)
            journal.queue.join()
    finally:
        journal.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["log", "log.1", "log.2"]
    assert json.loads(path.read_text())["monotonic"] == 15
    assert json.loads(Path(str(path) + ".2").read_text())["monotonic"] == 5


def test_log_io_failure_is_reported_without_breaking_observe(tmp_path):
    path = tmp_path / "not_a_directory"
    path.write_text("x")
    journal = HeartbeatDiagnostics(path / "log", dict, host=dict)
    message, motors = feedback()
    try:
        journal.observe(message, motors, 0)
        journal.queue.join()
        assert journal.error
    finally:
        journal.close()


def test_existing_can_callback_reports_processing_delay_without_swallowing_errors(
    monkeypatch,
):
    from component.can import can_bus

    bus = object.__new__(CanBus)
    callback = Mock(side_effect=ValueError("bad frame"))
    bus.silence = True
    bus.heartbeat_counts, bus.heartbeat_dispatch, bus.heartbeat_kernel = {}, {}, {}
    bus.listeners = {7: callback}
    bus.bus = NS(socket=None)
    bus.notifier = NS(exception=None)
    clock = iter((10, 10.02, 10.03))
    monkeypatch.setattr(can_bus.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(can_bus.time, "time", lambda: 100)
    message = NS(arbitration_id=7 << 5 | 1, timestamp=99.5)
    with pytest.raises(ValueError, match="bad frame"):
        read_message(bus, message)
    health = get_receive_health(bus)
    assert health["frames_processed"] == 1
    assert health["last_callback_ms"] == pytest.approx(20)
    assert health["kernel_to_callback_ms"] == pytest.approx(470)
    assert health["last_dispatch_age_ms"] == pytest.approx(30)
    callback.assert_called_once_with(message)


def test_command_counts_track_socket_acceptance_not_failed_sends():
    import can
    from component.can import can_bus

    bus = object.__new__(CanBus)
    bus.bus = Mock()
    assert can_bus.send_message(bus, 7 << 5 | 0x0C, b"")
    assert bus.tx_commands == {0x0C: 1}
    bus.bus.send.side_effect = can.CanOperationError("buffer full")
    assert not can_bus.send_message(bus, 7 << 5 | 0x0C, b"")
    assert bus.tx_commands == {0x0C: 1}


def test_short_outage_is_retained_even_if_heartbeat_returns_before_log_write(tmp_path):
    path = tmp_path / "log"
    journal = HeartbeatDiagnostics(path, dict, host=dict)
    message, motors = feedback()
    try:
        journal.observe(message, motors, 0)
        message.actuators[0].heartbeat_available = False
        journal.observe(message, motors, 0.1)
        message.actuators[0].heartbeat_available = True
        journal.observe(message, motors, 0.2)
        journal.observe(message, motors, 1)
        journal.queue.join()
    finally:
        journal.close()
    record = json.loads(path.read_text().splitlines()[-1])
    assert record["axes"][0]["heartbeat"] is True
    assert record["changes"] == {"fra:lost": 1, "fra:restored": 1}
    assert record["worst_missing_heartbeat"]["fra"]["heartbeat_age_ms"] == 100


def test_socket_memory_reports_queue_pressure_and_drops_without_receiving(monkeypatch):
    import struct
    from unittest.mock import Mock

    from component.can import can_bus

    monkeypatch.setattr(can_bus.sys, "platform", "linux")
    sock = Mock()
    sock.getsockopt.return_value = struct.pack(
        "=9I", 200000, 212992, 0, 212992, 0, 0, 0, 256, 37
    )
    assert can_bus.socket_memory_health(sock) == {
        "receive_allocated_bytes": 200000,
        "receive_limit_bytes": 212992,
        "backlog_bytes": 256,
        "drops_total": 37,
    }
    sock.recv.assert_not_called()
    sock.getsockopt.side_effect = OSError("unsupported")
    assert can_bus.socket_memory_health(sock) is None
    sock.getsockopt.side_effect = None
    sock.getsockopt.return_value = b"bad"
    assert can_bus.socket_memory_health(sock) is None
