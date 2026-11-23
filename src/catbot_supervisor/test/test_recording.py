import json

import pytest
from catbot_policy.recording import SessionRecorder


def test_segment_order_metadata_and_completed_rotation(tmp_path):
    first = SessionRecorder(
        tmp_path, {"policy_hash": "abc"}, segment_bytes=1, min_free_bytes=0
    )
    first.append("feedback", {"value": 1})
    first.append("action", {"value": 2})
    rows = [json.loads(p.read_text()) for p in sorted(first.path.glob("*.jsonl"))]
    assert [r["sequence"] for r in rows] == [0, 1]
    assert [r["kind"] for r in rows] == ["feedback", "action"]
    assert json.loads((first.path / "metadata.json").read_text()) == {
        "policy_hash": "abc"
    }
    active = SessionRecorder(tmp_path, {}, min_free_bytes=0, retain=1)
    assert first.path.exists()
    first.close()
    final = SessionRecorder(tmp_path, {}, min_free_bytes=0, retain=1)
    assert not first.path.exists() and active.path.exists()
    active.close()
    final.close()


def test_disk_reserve_and_mcap_selection(tmp_path):
    recorder = SessionRecorder(tmp_path, {}, min_free_bytes=10**30)
    with pytest.raises(OSError, match="reserve"):
        recorder.append("action", {})
    command = recorder.mcap_command(["/policy/action"])
    assert command[3:5] == ["-s", "mcap"]
    with pytest.raises(ValueError):
        recorder.mcap_command(["--all"])
    recorder.close()


def test_source_journal_freezes_payload_and_finishes_with_capture_status(tmp_path):
    from catbot_policy.recording import SourceJournal

    journal = SourceJournal(tmp_path, {"session": "test"})
    journal.recorder.min_free_bytes = 0
    payload = {"value": [1]}
    assert journal.submit("action", payload)
    payload["value"][0] = 2
    journal.close()
    rows = [
        json.loads(line)
        for file in sorted(journal.recorder.path.glob("*.jsonl"))
        for line in file.read_text().splitlines()
    ]
    assert rows[0]["payload"] == {"value": [1]}
    assert rows[-1]["payload"] == {"dropped": 0}
    assert (journal.recorder.path / "complete").exists()


def test_stalled_writer_has_bounded_close_and_source_timestamps(tmp_path, monkeypatch):
    import threading
    import time

    from catbot_policy import recording

    entered, release = threading.Event(), threading.Event()
    original = recording.SessionRecorder.append_encoded

    def blocked(self, data):
        entered.set()
        assert release.wait(2)
        original(self, data)

    monkeypatch.setattr(recording.SessionRecorder, "append_encoded", blocked)
    journal = recording.SourceJournal(tmp_path, {}, capacity=1)
    journal.recorder.min_free_bytes = 0
    monkeypatch.setattr(recording.time, "time_ns", lambda: 123)
    assert journal.submit("first", {})
    assert entered.wait(1)
    assert journal.submit("second", {})
    assert not journal.submit("overflow", {})
    monkeypatch.setattr(recording.time, "time_ns", lambda: 456)
    started = time.monotonic()
    journal.close(timeout=0.02)
    assert time.monotonic() - started < 0.5
    assert journal.status()["dropped"] == 1
    assert journal.error == "source journal shutdown timed out"
    assert not (journal.recorder.path / "complete").exists()
    release.set()
    journal.thread.join(timeout=2)
    assert not journal.thread.is_alive()
    rows = [
        json.loads(line)
        for p in journal.recorder.path.glob("*.jsonl")
        for line in p.read_text().splitlines()
    ]
    assert [row["wall_ns"] for row in rows[:2]] == [123, 123]
