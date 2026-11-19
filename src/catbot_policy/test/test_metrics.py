"""Window accounting and missing measurements without ROS bindings."""

import importlib.util
import math
import sys
from collections import deque
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def adapter(monkeypatch):
    modules = {
        "rclpy": {},
        "rclpy.node": {"Node": object},
        "rclpy.qos": dict.fromkeys(
            ("DurabilityPolicy", "QoSProfile", "ReliabilityPolicy"), Mock()
        ),
        "geometry_msgs.msg": {"Twist": object},
        "std_msgs.msg": {"String": object},
        "catbot_interfaces.msg": {
            "ActuatorPositionCommand": object,
            "PolicyAction": object,
            "PolicyActionAck": object,
            "PolicyReady": SimpleNamespace,
            "PolicyFeedback": object,
            "PolicyMetrics": SimpleNamespace,
        },
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).parents[1] / "catbot_policy/node.py"
    spec = importlib.util.spec_from_file_location("metrics_adapter_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "monotonic", lambda: 15.0)
    monkeypatch.setattr(module.time, "process_time", lambda: 22.0)
    monkeypatch.setattr(
        module.resource, "getrusage", lambda _: SimpleNamespace(ru_maxrss=50000)
    )
    node = SimpleNamespace(
        metrics_started=10.0,
        adapter_cpu_started=20.0,
        worker=SimpleNamespace(ready={"device": "cpu"}),
        dt=0.02,
        samples=deque([(1.0, 3.0, 5.0), (2.0, 4.0, 6.0)]),
        published=2,
        missed=3,
        busy_ticks=4,
        discarded=5,
        worker_rss=260000,
        worker_cpu=12.0,
        worker_cpu_previous=7.0,
        metrics=Mock(),
        get_clock=lambda: SimpleNamespace(
            now=lambda: SimpleNamespace(to_msg=lambda: "publication stamp")
        ),
    )
    return module.PolicyNode.report_metrics, node


def test_typed_metrics_window_and_reset(adapter):
    report, node = adapter
    report(node)
    message = node.metrics.publish.call_args.args[0]
    assert message.stamp == "publication stamp"
    assert message.window_seconds == 5.0
    assert message.control_interval_ms == 20.0
    assert message.published_hz == 0.4
    assert message.sample_count == 2
    assert message.inference_p50_ms == 1.0
    assert message.round_trip_p95_ms == 3.0
    assert message.feedback_age_p99_ms == 5.0
    assert message.adapter_cpu_percent_one_core == 40.0
    assert message.worker_cpu_percent_one_core == 100.0
    assert message.worker_peak_rss_kib == 260000.0
    assert (
        message.missed_timer_intervals,
        message.busy_ticks,
        message.discarded_results,
    ) == (3, 4, 5)
    assert not node.samples
    assert (node.published, node.missed, node.busy_ticks, node.discarded) == (
        0,
        0,
        0,
        0,
    )
    assert node.worker_cpu_previous == 12.0
    assert node.metrics_started == 15.0


def test_empty_window_and_unavailable_worker_stats(adapter):
    report, node = adapter
    node.samples.clear()
    node.published = 0
    node.worker_cpu_previous = None
    node.worker_rss = None
    report(node)
    message = node.metrics.publish.call_args.args[0]
    assert message.sample_count == 0
    assert message.published_hz == 0.0
    for prefix in ("inference", "round_trip", "feedback_age"):
        for percentile in ("p50", "p95", "p99"):
            assert math.isnan(getattr(message, f"{prefix}_{percentile}_ms"))
    assert math.isnan(message.worker_cpu_percent_one_core)
    assert math.isnan(message.worker_peak_rss_kib)


def test_first_worker_cpu_measurement_is_not_a_zero(adapter):
    report, node = adapter
    node.worker_cpu = None
    node.worker_cpu_previous = None
    report(node)
    assert math.isnan(
        node.metrics.publish.call_args.args[0].worker_cpu_percent_one_core
    )


@pytest.mark.parametrize("forwarded", [True, False])
def test_pi_acknowledgement_controls_worker_history(adapter, forwarded):
    report, node = adapter
    node.action_session = "session"
    node.worker.send = Mock()
    node.pending = {
        "id": 20,
        "gate_sequence": 7,
        "gate_acknowledged": False,
        "accepted": False,
        "sample": (1, 2, 3),
    }
    ack = report.__globals__["PolicyNode"].action_ack
    before = (node.published, node.discarded, len(node.samples))
    ack(node, SimpleNamespace(session="old", sequence=7, forwarded=True))
    ack(node, SimpleNamespace(session="session", sequence=6, forwarded=True))
    node.worker.send.assert_not_called()
    message = SimpleNamespace(session="session", sequence=7, forwarded=forwarded)
    ack(node, message)
    ack(node, message)
    node.worker.send.assert_called_once_with(
        {"type": "ack", "id": 20, "published": forwarded}
    )
    assert node.pending["accepted"] == forwarded
    assert node.published == before[0] + int(forwarded)
    assert node.discarded == before[1] + int(not forwarded)
    assert len(node.samples) == before[2] + int(forwarded)


@pytest.mark.parametrize("verified", [True, False])
def test_readiness_requires_runtime_verification(adapter, verified):
    report, node = adapter
    node.action_session = "session"
    node.ready_publisher = Mock()
    node.worker.ready = {"bundle_id": "a" * 64, "verified": verified}
    report.__globals__["PolicyNode"]._publish_ready(node, True, "ready")
    message = node.ready_publisher.publish.call_args.args[0]
    assert message.session == "session" and message.bundle_id == "a" * 64
    assert message.ready is verified and message.verified is verified


def test_hardware_provider_contract_mismatch_blocks_readiness(adapter):
    report, node = adapter
    node.requires_contract = True
    node.contract_ready = True
    node.metadata = {"model_sha256": "expected", "policy_contract": {}, "settings": {}}
    node.mapping = {}
    node._publish_ready = Mock()
    with pytest.raises(ValueError, match="Provider model"):
        report.__globals__["PolicyNode"].contract_callback(
            node, SimpleNamespace(data='{"version":1,"model_sha256":"wrong"}')
        )
    assert not node.contract_ready
    node._publish_ready.assert_called_once_with(False, "provider contract mismatch")
