import pytest
from catbot_supervisor.health import PiHealth, health_reason


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def process(proc, ticks, started=100):
    fields = ["0"] * 40
    fields[11], fields[12], fields[19] = str(ticks), "0", str(started)
    write(proc / "42/stat", "42 (foundation main) " + " ".join(fields))
    write(proc / "42/cmdline", "/usr/bin/python3\0/install/lib/foundation/main\0")


def test_health_cpu_temperature_interface_and_process_restart(tmp_path):
    proc, sys = tmp_path / "proc", tmp_path / "sys"
    write(proc / "stat", "cpu 10 0 0 90 0 0 0 0 0 0\n")
    write(sys / "class/net/test0/operstate", "up")
    write(sys / "class/thermal/thermal_zone0/temp", "55000")
    process(proc, 10)
    health = PiHealth(interface="test0", proc=proc, sys=sys)
    health.ticks_per_second = 100
    first = health.sample(1)
    assert first["foundation_cpu_percent_one_core"] is None
    assert health_reason(first, min_headroom=20, max_temperature=65)
    process(proc, 30)
    write(proc / "stat", "cpu 30 0 0 170 0 0 0 0 0 0\n")
    sample = health.sample(2)
    assert sample["system_cpu_headroom_percent"] == 80
    assert sample["foundation_cpu_percent_one_core"] == 20
    assert sample["temperature_c"] == 55
    assert sample["interface_state"] == "up"
    assert not health_reason(sample, min_headroom=20, max_temperature=65)
    process(proc, 40, started=200)
    assert health.sample(3)["foundation_cpu_percent_one_core"] is None


def test_missing_health_is_explicit_unknown(tmp_path):
    sample = PiHealth(proc=tmp_path, sys=tmp_path).sample(1)
    assert sample["interface_state"] == "unknown"
    for field in (
        "temperature_c",
        "system_cpu_headroom_percent",
        "foundation_cpu_percent_one_core",
    ):
        assert sample[field] is None
    assert {error.split(":", 1)[0] for error in sample["errors"]} >= {
        "cpu",
        "foundation",
        "network",
        "temperature",
    }
    assert "unavailable" in health_reason(sample)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("interface_state", "down", "network"),
        ("temperature_c", 66, "temperature"),
        ("system_cpu_headroom_percent", 19, "headroom"),
        ("foundation_cpu_percent_one_core", None, "Foundation"),
    ],
)
def test_unhealthy_samples_prevent_ready(field, value, reason):
    sample = {
        "errors": [],
        "interface_state": "up",
        "temperature_c": 50,
        "system_cpu_headroom_percent": 80,
        "foundation_cpu_percent_one_core": 10,
    }
    assert not health_reason(sample, min_headroom=20, max_temperature=65)
    sample[field] = value
    assert reason in health_reason(sample, min_headroom=20, max_temperature=65)


def test_interface_path_traversal_is_rejected():
    with pytest.raises(ValueError):
        PiHealth(interface="../etc")
