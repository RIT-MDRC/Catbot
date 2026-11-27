"""Bounded, background heartbeat diagnostics; no additional CAN/ROS receivers."""

import json
import os
import queue
import threading
import time
from pathlib import Path


def host_health():
    result = {"process_cpu_seconds": time.process_time(), "pid": os.getpid()}
    counters = {}
    for name in (
        "rx_packets",
        "rx_dropped",
        "rx_errors",
        "rx_over_errors",
        "tx_packets",
        "tx_errors",
    ):
        try:
            counters[name] = int(
                (Path("/sys/class/net/can0/statistics") / name).read_text()
            )
        except OSError:
            counters[name] = None
    result["can0"] = counters
    try:
        result["load_average"] = list(os.getloadavg())
    except OSError:
        result["load_average"] = None
    return result


class HeartbeatDiagnostics:
    def __init__(
        self,
        path,
        receive_health,
        *,
        host=host_health,
        max_bytes=5 * 1024 * 1024,
        queue_size=32,
    ):
        self.path = Path(path).expanduser()
        self.receive_health, self.host, self.max_bytes = receive_health, host, max_bytes
        self.queue = queue.Queue(maxsize=queue_size)
        self.stop = threading.Event()
        self.error = ""
        self.dropped = 0
        self.pattern = None
        self.changes = {}
        self.loss_peaks = {}
        self.last_record = float("-inf")
        self.thread = threading.Thread(
            target=self._write, name="heartbeat-diagnostics", daemon=True
        )
        self.thread.start()

    def observe(self, message, motors, now=None):
        now = time.monotonic() if now is None else now
        pattern = tuple(a.heartbeat_available for a in message.actuators)
        initial = self.pattern is None
        if self.pattern is not None and pattern != self.pattern:
            for a, before in zip(message.actuators, self.pattern):
                if before != a.heartbeat_available:
                    key = f"{a.actuator_name}:{'restored' if a.heartbeat_available else 'lost'}"
                    self.changes[key] = self.changes.get(key, 0) + 1
        self.pattern = pattern
        for axis in message.actuators:
            if not axis.heartbeat_available:
                heartbeat = motors[axis.actuator_name].last_heartbeat_time
                age = None if heartbeat is None else (now - heartbeat) * 1000
                previous = self.loss_peaks.get(axis.actuator_name)
                if (
                    previous is None
                    or age is not None
                    and (
                        previous["heartbeat_age_ms"] is None
                        or age > previous["heartbeat_age_ms"]
                    )
                ):
                    self.loss_peaks[axis.actuator_name] = {
                        "monotonic": now,
                        "heartbeat_age_ms": age,
                        "state": axis.axis_state,
                        "axis_error_flags": axis.axis_error_flags,
                    }
        if now - self.last_record < (1.0 if self.changes else 5.0):
            return
        axes = []
        for a in message.actuators:
            motor = motors[a.actuator_name]
            hb = motor.last_heartbeat_time
            encoder = motor.last_encoder_estimate_time
            axes.append(
                {
                    "name": a.actuator_name,
                    "axis_id": a.axis_id,
                    "state": a.axis_state,
                    "heartbeat": a.heartbeat_available,
                    "ready": a.ready,
                    "heartbeat_age_ms": None if hb is None else (now - hb) * 1000,
                    "encoder_age_ms": None
                    if encoder is None
                    else (now - encoder) * 1000,
                    "faults": {
                        field: {
                            "flags": getattr(a, field + "_error_flags"),
                            "messages": list(getattr(a, field + "_error_messages")),
                        }
                        for field in (
                            "axis",
                            "motor",
                            "encoder",
                            "sensorless",
                            "controller",
                        )
                    },
                }
            )
        record = {
            "version": 1,
            "event": "startup"
            if initial
            else "heartbeat_change"
            if self.changes
            else "periodic",
            "wall_time": time.time(),
            "monotonic": now,
            "changes": dict(self.changes),
            "axes": axes,
            "worst_missing_heartbeat": dict(self.loss_peaks),
            "queue_dropped": self.dropped,
        }
        self.last_record = now
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1
        else:
            self.changes.clear()
            self.loss_peaks.clear()

    def _write(self):
        while not self.stop.is_set() or not self.queue.empty():
            try:
                record = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                record["written_wall_time"] = time.time()
                record["writer_delay_ms"] = (
                    time.monotonic() - record["monotonic"]
                ) * 1000
                record["host"] = self.host()
                record["receive"] = self.receive_health()
                text = json.dumps(record, allow_nan=False)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                    first, second = (
                        Path(str(self.path) + ".1"),
                        Path(str(self.path) + ".2"),
                    )
                    if first.exists():
                        first.replace(second)
                    self.path.replace(first)
                with self.path.open("a") as stream:
                    stream.write(text + "\n")
            except (
                OSError,
                ValueError,
                TypeError,
                RuntimeError,
                AttributeError,
            ) as error:
                # Diagnostic failure must never stop motor state processing.
                self.error = str(error)
            finally:
                self.queue.task_done()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1.0)
