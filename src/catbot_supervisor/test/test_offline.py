from unittest.mock import Mock

import pytest
from catbot_supervisor.offline import OfflineQueue


def test_queue_is_bounded_coalesced_and_allowlisted():
    queue = OfflineQueue({"eval": ["eval"], "replay": ["replay"]}, max_pending=1)
    queue.enqueue("eval")
    queue.enqueue("eval")
    with pytest.raises(ValueError, match="full"):
        queue.enqueue("replay")
    with pytest.raises(ValueError, match="Unknown"):
        queue.enqueue("shell")
    assert queue.status()["pending"] == ["eval"]


def test_work_starts_only_when_idle_and_is_cancelled_before_policy(monkeypatch):
    child = Mock(pid=123)
    child.poll.return_value = None
    spawn = Mock(return_value=child)
    signal = Mock()
    monkeypatch.setattr("subprocess.Popen", spawn)
    monkeypatch.setattr("os.killpg", signal)
    queue = OfflineQueue({"eval": ["eval"], "replay": ["replay"]})
    queue.enqueue("eval")
    queue.enqueue("replay")
    queue.tick(1, idle=True)
    assert queue.active == "eval"
    queue.tick(2, idle=False)
    assert not queue.pending
    assert not queue.jobs.running("eval")
    assert signal.call_count == 1
    child.poll.return_value = 0
    queue.tick(5, idle=False)
    queue.tick(7, idle=False)
    assert queue.active is None
    assert spawn.call_count == 1
