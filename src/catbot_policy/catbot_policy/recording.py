"""Segmented, recoverable source journal and explicit MCAP capture commands."""

import json
import math
import os
import queue
import shutil
import threading
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
        if (
            any(
                type(value) is not int
                for value in (segment_bytes, min_free_bytes, retain)
            )
            or segment_bytes < 1
            or min_free_bytes < 0
            or retain < 1
        ):
            raise ValueError("invalid recording limits")
        encoded_metadata = json.dumps(metadata, allow_nan=False, indent=2)
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.segment_bytes, self.min_free_bytes = segment_bytes, min_free_bytes
        self.path = self.root / (
            time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex
        )
        self.path.mkdir()
        self.stream = None
        self.index = self.sequence = 0
        (self.path / "metadata.json").write_text(encoded_metadata)
        completed = sorted(
            p for p in self.root.iterdir() if p.is_dir() and (p / "complete").is_file()
        )
        for old in completed[: max(0, len(completed) - retain + 1)]:
            shutil.rmtree(old)

    def append(self, kind, payload):
        self.append_encoded(encode_event(kind, payload, self.sequence))

    def append_encoded(self, data):
        """Write a frozen UTF-8 JSONL event without serializing it again."""
        if shutil.disk_usage(self.root).free < self.min_free_bytes:
            raise OSError("recording disk reserve reached")
        if self.stream is None or self.stream.tell() + len(data) > self.segment_bytes:
            self._close_segment()
            self.stream = (self.path / f"source-{self.index:06d}.jsonl").open("ab")
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


def encode_event(kind, payload, sequence):
    """Freeze source values and capture clocks before any writer queue delay."""
    return (
        json.dumps(
            {
                "sequence": sequence,
                "kind": kind,
                "wall_ns": time.time_ns(),
                "monotonic_ns": time.monotonic_ns(),
                "payload": payload,
            },
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


class SourceJournal:
    """Single-producer capture with bounded memory and bounded shutdown waiting."""

    def __init__(self, root, metadata, capacity=1024):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("journal capacity must be positive")
        self.queue = queue.Queue(maxsize=capacity)
        self.recorder = SessionRecorder(root, metadata)
        self.dropped = 0
        self.error = ""
        self.closed = False
        self.sequence = 0
        self.high_watermark = 0
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()

    def submit(self, kind, payload):
        if self.closed or self.error or self.queue.full():
            self.dropped += 1
            return False
        try:
            self.queue.put_nowait(encode_event(kind, payload, self.sequence))
        except queue.Full:
            self.dropped += 1
            return False
        self.sequence += 1
        self.high_watermark = max(self.high_watermark, self.queue.qsize())
        return True

    def status(self):
        return {
            "submitted": self.sequence,
            "written_records": self.recorder.sequence,
            "capacity": self.queue.maxsize,
            "writer_alive": self.thread.is_alive(),
            "dropped": self.dropped,
            "error": self.error,
            "queue_depth": self.queue.qsize(),
            "high_watermark": self.high_watermark,
        }

    def _write(self):
        try:
            while not self.stopping.is_set() or not self.queue.empty():
                try:
                    item = self.queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self.recorder.append_encoded(item)
            self.recorder.append("capture_status", {"dropped": self.dropped})
            self.recorder.close()
        except (OSError, ValueError) as error:
            self.error = str(error)
            try:
                self.recorder._close_segment()
            except (OSError, ValueError):
                pass  # Preserve the original write error; leave the session incomplete.

    def close(self, timeout=5.0):
        """A stalled filesystem can outlive this wait, but cannot block shutdown."""
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("journal close timeout must be finite and nonnegative")
        self.closed = True
        self.stopping.set()
        self.thread.join(timeout=timeout)
        if self.thread.is_alive():
            self.error = "source journal shutdown timed out"
