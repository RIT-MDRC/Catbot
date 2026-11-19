import signal
import subprocess
import sys
from unittest.mock import Mock

import pytest
from catbot_supervisor.jobs import Jobs


@pytest.mark.parametrize(
    "commands", [{"bad": "shell"}, {"bad": []}, {"": ["cmd"]}, {"bad": ["cmd", 2]}]
)
def test_jobs_reject_unregistered_or_malformed_commands(commands):
    with pytest.raises(ValueError):
        Jobs(commands)


def test_only_registered_jobs_start_and_repeated_start_is_idempotent(monkeypatch):
    child = Mock(pid=123)
    child.poll.return_value = None
    spawn = Mock(return_value=child)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    jobs = Jobs({"record": ["recorder", "--output", "/tmp/file"]})
    with pytest.raises(ValueError):
        jobs.start("unknown")
    jobs.start("record")
    jobs.start("record")
    assert jobs.running("record")
    spawn.assert_called_once_with(
        ["recorder", "--output", "/tmp/file"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
    )


def test_stop_escalates_and_cleans_descendants_after_leader_exit(monkeypatch):
    child = Mock(pid=123)
    child.poll.return_value = None
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=child))
    signals = []
    monkeypatch.setattr("os.killpg", lambda pid, sig: signals.append((pid, sig)))
    jobs = Jobs({"policy": ["policy"]})
    jobs.start("policy")
    jobs.stop("policy", 1)
    assert not jobs.running("policy")
    jobs.start("policy", 1)
    assert jobs.status("policy")["policy"]["state"] == "restarting"
    jobs.stop("policy", 1)
    jobs.tick(4)
    child.poll.return_value = 0
    jobs.tick(6)
    assert signals == [
        (123, signal.SIGINT),
        (123, signal.SIGTERM),
        (123, signal.SIGKILL),
    ]
    assert not jobs.children


def test_actual_local_job_is_reaped_on_close():
    jobs = Jobs({"worker": [sys.executable, "-c", "import time; time.sleep(30)"]})
    try:
        jobs.start("worker")
        child = jobs.children["worker"]
        assert jobs.running("worker")
    finally:
        jobs.close()
    assert child.poll() is not None
    assert not jobs.children


def test_restart_is_coalesced_and_rechecks_preflight_before_new_process(monkeypatch):
    children = [Mock(pid=123), Mock(pid=124)]
    children[0].poll.return_value = None
    children[1].poll.return_value = None
    spawn = Mock(side_effect=children)
    prepare = Mock()
    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr("os.killpg", Mock())
    jobs = Jobs({"policy": ["policy"]}, before_start=prepare)
    jobs.start("policy", 0)
    jobs.restart("policy", 1)
    jobs.restart("policy", 2)
    assert spawn.call_count == 1
    jobs.tick(4)
    children[0].poll.return_value = 0
    jobs.tick(6)
    assert spawn.call_count == 2 and prepare.call_count == 2
    assert jobs.children["policy"].pid == 124
    jobs.restart("policy", 7)
    jobs.stop("policy", 7)
    jobs.tick(10)
    children[1].poll.return_value = 0
    jobs.tick(12)
    assert not jobs.pending and spawn.call_count == 2


def test_queued_restart_fails_closed_if_preflight_changes(monkeypatch):
    child = Mock(pid=1)
    child.poll.return_value = None
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=child))
    monkeypatch.setattr("os.killpg", Mock())
    prepare = Mock(side_effect=[None, ValueError("clock skew")])
    jobs = Jobs({"policy": ["worker"]}, before_start=prepare)
    jobs.start("policy")
    jobs.restart("policy", 0)
    jobs.tick(3)
    child.poll.return_value = 0
    jobs.tick(5)
    assert jobs.status("policy")["policy"]["state"] == "failed"
    assert "clock skew" in jobs.status("policy")["policy"]["error"]
