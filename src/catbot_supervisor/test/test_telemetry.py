import time
from pathlib import Path

import pytest
from catbot_policy.configuration import POLICY_DEFAULTS
from catbot_supervisor.preflight import ComputeProbe
from catbot_supervisor.telemetry import Resources


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def test_linux_and_jetson_resources_report_unknown_without_fabrication(tmp_path):
    proc, sys = tmp_path / "proc", tmp_path / "sys"
    put(proc / "stat", "cpu 10 0 0 90 0 0 0 0\n")
    put(proc / "meminfo", "MemTotal: 1000 kB\nMemAvailable: 300 kB\n")
    put(sys / "class/thermal/thermal_zone0/temp", "55000")
    put(sys / "class/devfreq/17000000.ga10b/device/load", "350")
    resources = Resources(str(tmp_path), proc, sys)
    first = resources.sample()
    assert first["cpu_percent"] is None
    assert first["gpu_percent"] == 35 and first["temperature_c"] == 55
    assert first["memory_used_bytes"] == 700 * 1024 and not first["errors"]
    put(proc / "stat", "cpu 30 0 0 170 0 0 0 0\n")
    assert resources.sample()["cpu_percent"] == pytest.approx(20)
    missing = Resources(
        str(tmp_path / "absent"), tmp_path / "missing", tmp_path / "missing"
    ).sample()
    assert missing["gpu_percent"] is None and len(missing["errors"]) == 3


def test_compute_probe_uses_isolated_worker_and_finishes_without_ros_blocking(tmp_path):
    fake = Path(__file__).parents[3] / "tests/fixtures/fake_worker.py"
    parameters = {
        **POLICY_DEFAULTS,
        "policy_worker_project": str(tmp_path),
        "policy_uv_executable": str(fake),
    }
    probe = ComputeProbe(parameters)
    try:
        probe.start(time.monotonic())
        deadline = time.monotonic() + 3
        while probe.child is not None and time.monotonic() < deadline:
            probe.tick(time.monotonic())
            time.sleep(0.01)
        assert probe.available and not probe.reason
    finally:
        probe.close()
