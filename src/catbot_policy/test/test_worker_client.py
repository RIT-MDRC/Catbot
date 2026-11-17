"""Real pipes/process groups with no uv, torch, or ROS worker dependency."""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest
from catbot_policy.worker_client import WorkerClient
from catbot_policy.worker_launch import WorkerLaunchSpec

FAKE = Path(__file__).resolve().parents[3] / "tests/fixtures/fake_worker.py"


@pytest.fixture
def worker_factory(tmp_path, monkeypatch):
    (tmp_path / "run_worker.py").touch()
    (tmp_path / "uv.lock").touch()
    children = []
    real_popen = subprocess.Popen

    def spawn(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr(
        WorkerLaunchSpec,
        "build",
        lambda *a, **k: WorkerLaunchSpec(
            [sys.executable, str(FAKE)], os.environ.copy()
        ),
    )
    clients = []

    def make(mode):
        monkeypatch.setenv("FAKE_WORKER_MODE", mode)
        client = WorkerClient(tmp_path, "", "unused", "", "", 0.25, 1, 0.3)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
    assert all(child.poll() is not None for child in children), "Leaked worker process"


@pytest.mark.parametrize(
    ("mode", "error"),
    [
        ("timeout", "timed out"),
        ("oversized", "oversized"),
        ("version", "Unsupported"),
        ("malformed", "Expecting"),
        ("array", "Unsupported"),
    ],
)
def test_invalid_startup_reaps_worker(worker_factory, mode, error):
    with pytest.raises(RuntimeError, match=error):
        worker_factory(mode)


def test_protocol_round_trip(worker_factory):
    client = worker_factory("ready")
    client.send({"type": "ping", "id": 7})
    assert client.events.get(timeout=2)["request"] == {
        "version": 1,
        "type": "ping",
        "id": 7,
    }
    client.close()
    client.close()
    assert not client.thread.is_alive()


def test_shutdown_escalates_to_sigkill(worker_factory):
    client = worker_factory("ignore_term")
    client.close()
    assert client.process.returncode == -signal.SIGKILL
    assert not client.thread.is_alive()
