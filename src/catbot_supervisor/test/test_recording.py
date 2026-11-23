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
