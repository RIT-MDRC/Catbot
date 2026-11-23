"""Segmented, recoverable source journal and explicit MCAP capture commands."""

import json
import os
import shutil
import time
import uuid
from pathlib import Path


class SessionRecorder:
    def __init__(
        self,
        root,
        metadata,
        *,
        segment_bytes=16777216,
        min_free_bytes=1073741824,
        retain=10,
    ):
        if segment_bytes < 1 or min_free_bytes < 0 or retain < 1:
            raise ValueError("invalid recording limits")
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.segment_bytes, self.min_free_bytes = segment_bytes, min_free_bytes
        self.path = self.root / (
            time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex
        )
        self.path.mkdir()
        self.stream = None
        self.index = self.sequence = 0
        (self.path / "metadata.json").write_text(
            json.dumps(metadata, allow_nan=False, indent=2)
        )
        completed = sorted(
            p for p in self.root.iterdir() if p.is_dir() and (p / "complete").is_file()
        )
        for old in completed[: max(0, len(completed) - retain + 1)]:
            shutil.rmtree(old)

    def append(self, kind, payload):
        if shutil.disk_usage(self.root).free < self.min_free_bytes:
            raise OSError("recording disk reserve reached")
        data = (
            json.dumps(
                {
                    "sequence": self.sequence,
                    "kind": kind,
                    "wall_ns": time.time_ns(),
                    "monotonic_ns": time.monotonic_ns(),
                    "payload": payload,
                },
                allow_nan=False,
            )
            + "\n"
        )
        if (
            self.stream is None
            or self.stream.tell() + len(data.encode()) > self.segment_bytes
        ):
            self._close_segment()
            self.stream = (self.path / f"source-{self.index:06d}.jsonl").open("a")
            self.index += 1
        self.stream.write(data)
        self.stream.flush()
        self.sequence += 1

    def _close_segment(self):
        if self.stream is not None:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()
            self.stream = None

    def close(self):
        self._close_segment()
        (self.path / "complete").touch()

    def mcap_command(self, topics, *, duration=60, size=268435456):
        if not topics or any(
            not isinstance(t, str) or not t.startswith("/") for t in topics
        ):
            raise ValueError("explicit absolute recording topics required")
        if duration <= 0 or size <= 0:
            raise ValueError("positive split limits required")
        return [
            "ros2",
            "bag",
            "record",
            "-s",
            "mcap",
            "-o",
            str(self.path / "mcap"),
            "--max-bag-duration",
            str(duration),
            "--max-bag-size",
            str(size),
            *topics,
        ]


class SourceJournal:
    """Bounded writer thread: disk work cannot delay the control callback."""

    def __init__(self, root, metadata, capacity=1024):
        import queue
        import threading

        self.queue = queue.Queue(maxsize=capacity)
        self.recorder = SessionRecorder(root, metadata)
        self.dropped = 0
        self.error = ""
        self.closed = False
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()

    def submit(self, kind, payload):
        import queue

        if self.closed or self.error:
            self.dropped += 1
            return False
        # Serialize now to freeze source values before the next callback mutates them.
        item = json.loads(json.dumps([kind, payload], allow_nan=False))
        try:
            self.queue.put_nowait(item)
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _write(self):
        try:
            while True:
                item = self.queue.get()
                if item is None:
                    break
                self.recorder.append(*item)
            self.recorder.append("capture_status", {"dropped": self.dropped})
            self.recorder.close()
        except (OSError, ValueError) as error:
            self.error = str(error)
            self.recorder._close_segment()

    def close(self):
        import queue

        self.closed = True
        while self.thread.is_alive():
            try:
                self.queue.put(None, timeout=0.1)
                break
            except queue.Full:
                continue
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.error = "source journal shutdown timed out"
