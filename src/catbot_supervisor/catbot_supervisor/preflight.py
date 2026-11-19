"""Clock offset bounds and a bounded compute probe in the inference environment."""

import contextlib
import json
import math
import os
import signal
import subprocess
import tempfile
from pathlib import Path

from catbot_policy.configuration import inference_python
from catbot_policy.worker_launch import WorkerLaunchSpec


def seconds(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


class ClockMonitor:
    def __init__(self, tolerance=0.02, max_age=2.0, max_rtt=0.15):
        if not all(math.isfinite(v) and v > 0 for v in (tolerance, max_age, max_rtt)):
            raise ValueError("Clock limits must be positive and finite")
        self.tolerance, self.max_age, self.max_rtt = tolerance, max_age, max_rtt
        self.pending = {}
        self.offset = self.uncertainty = self.received = None
        self.reason = "clock exchange unavailable"

    def sent(self, identity, wall, now):
        self.pending = {
            key: value
            for key, value in self.pending.items()
            if now - value[1] <= self.max_age
        }
        self.pending[identity] = wall, now

    def reply(self, identity, origin, received, sent, wall_now, now):
        previous = self.pending.pop(identity, None)
        if previous is None:
            return False
        start, started_at = previous
        elapsed = now - started_at
        processing = sent - received
        if (
            origin != start
            or not all(math.isfinite(v) for v in (origin, received, sent, wall_now))
            or not 0 <= elapsed <= self.max_rtt
            or processing < 0
            or processing > elapsed + 0.001
            or abs((wall_now - start) - elapsed) > 0.005
        ):
            self.reason = "invalid clock exchange or local clock step"
            self.received = None
            return False
        self.offset = ((received - start) + (sent - wall_now)) / 2
        self.uncertainty = max(0.0, (elapsed - processing) / 2)
        self.received = now
        self.reason = ""
        return True

    def verdict(self, now):
        if self.received is None or not 0 <= now - self.received <= self.max_age:
            return self.reason or "clock exchange stale"
        if (
            self.offset is None
            or self.uncertainty is None
            or abs(self.offset) + self.uncertainty > self.tolerance
        ):
            return "Pi clock skew bound exceeds tolerance"
        return ""

    def status(self, now):
        return {
            "offset_seconds": self.offset,
            "uncertainty_seconds": self.uncertainty,
            "reason": self.verdict(now),
        }


class ComputeProbe:
    """One finite probe. No PyTorch import or blocking wait in the ROS process."""

    def __init__(self, parameters, timeout=30.0):
        self.parameters, self.timeout = parameters, timeout
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Compute probe timeout must be positive and finite")
        self.files = contextlib.ExitStack()
        self.child = self.output = self.started = None
        self.available = False
        self.reason = "compute probe pending"

    def start(self, now):
        p = self.parameters
        try:
            project = Path(str(p["policy_worker_project"])).expanduser()
            device = str(p["policy_device"])
            environment, sync = WorkerLaunchSpec.resolve(
                device, project, p["policy_worker_environment"], p["policy_worker_sync"]
            )
            if device.startswith("cuda"):
                if sync:
                    raise ValueError("CUDA preflight requires its prepared environment")
                project = project / "cuda"
            spec = WorkerLaunchSpec.build(
                project,
                str(p["policy_uv_executable"]),
                [
                    str(
                        Path(str(p["policy_worker_project"])).expanduser()
                        / "run_worker.py"
                    ),
                    "--preflight",
                ],
                device=device,
                environment=environment,
                sync=sync,
                python=inference_python(device, str(p["policy_python"])),
            )
            self.output = self.files.enter_context(tempfile.TemporaryFile())  # noqa: SIM115 - ExitStack owns process-lifetime output
            self.child = subprocess.Popen(
                spec.command,
                env=spec.environment,
                stdin=subprocess.DEVNULL,
                stdout=self.output,
                start_new_session=True,
            )
            self.started = now
        except (OSError, ValueError) as error:
            self.reason = str(error)
            self.close()

    def tick(self, now):
        if self.child is None:
            return
        code = self.child.poll()
        if code is None and now - self.started < self.timeout:
            return
        if code is None:
            self.reason = "compute probe timed out"
            self.close()
            return
        if self.output is None:
            raise RuntimeError("Compute probe has no output stream")
        self.output.seek(0)
        raw = self.output.read(131073)
        try:
            result = json.loads(raw)
            self.available = (
                code == 0
                and result.get("type") == "preflight"
                and result.get("available") is True
                and result.get("device") == str(self.parameters["policy_device"])
            )
            self.reason = "" if self.available else "compute device unavailable"
        except (ValueError, AttributeError):
            self.reason = "invalid compute probe response"
        self.close()

    def close(self):
        if self.child is not None:
            try:
                os.killpg(self.child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.child.wait(timeout=3)
            self.child = None
        if self.output is not None:
            self.files.close()
            self.output = None


def verdict(resources, clock, compute, now, max_temperature, min_disk):
    if resources is None:
        return "resource sample unavailable"
    if resources["errors"]:
        return "; ".join(resources["errors"])
    if (
        resources["temperature_c"] is None
        or resources["temperature_c"] >= max_temperature
    ):
        return "Orin temperature exceeds limit"
    if resources["disk_free_bytes"] < min_disk:
        return "Orin disk space below limit"
    if not compute.available:
        return compute.reason
    return clock.verdict(now)
