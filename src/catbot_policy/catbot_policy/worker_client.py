"""Bounded JSON-lines subprocess transport; stdlib only, compatible with ROS Python."""

import json
import os
import queue
import signal
import subprocess
import threading
from pathlib import Path

from catbot_policy.protocol import MAX_LINE_BYTES, VERSION


class WorkerClient:
    def __init__(
        self,
        project,
        python,
        uv,
        bundle,
        mapping,
        feedback_timeout,
        ack_timeout,
        startup_timeout,
    ):
        project = Path(project).expanduser().resolve()
        runner = project / "run_worker.py"
        if not runner.is_file() or not (project / "uv.lock").is_file():
            raise ValueError(
                "policy_worker_project needs the initialized inference uv project"
            )
        command = [
            uv,
            "run",
            "--locked",
            "--project",
            str(project),
            "--python",
            python,
            "python",
            str(runner),
            "--bundle",
            bundle,
            "--feedback-timeout",
            str(feedback_timeout),
            "--ack-timeout",
            str(ack_timeout),
        ]
        if mapping:
            command += ["--mapping", mapping]
        env = os.environ.copy()
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "VIRTUAL_ENV",
            "UV_PROJECT_ENVIRONMENT",
        ):
            env.pop(name, None)
        self.closed = False
        self.events = queue.Queue(maxsize=8)
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
            env=env,
        )
        self.stdin, self.stdout = self.process.stdin, self.process.stdout
        if self.stdin is None or self.stdout is None:
            raise RuntimeError("Failed to create policy protocol pipes")
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        try:
            self.ready = self.events.get(timeout=startup_timeout)
            if self.ready.get("type") != "ready":
                raise RuntimeError(
                    self.ready.get("error", "Worker failed to initialize")
                )
        except queue.Empty as error:
            self.close()
            raise RuntimeError("Policy worker initialization timed out") from error
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            if self.stdout is None:
                raise RuntimeError("No worker stdout")
            while True:
                line = self.stdout.readline(MAX_LINE_BYTES + 1)
                if not line:
                    raise RuntimeError("Policy worker exited")
                if len(line.encode()) > MAX_LINE_BYTES or not line.endswith("\n"):
                    raise ValueError("Invalid or oversized worker response")
                value = json.loads(line)
                if not isinstance(value, dict) or value.get("version") != VERSION:
                    raise ValueError("Unsupported worker protocol")
                self.events.put_nowait(value)
        except (OSError, ValueError, RuntimeError, queue.Full) as error:
            try:
                self.events.put_nowait({"type": "error", "error": str(error)})
            except queue.Full:
                pass

    def send(self, message):
        line = json.dumps({"version": VERSION, **message}, allow_nan=False) + "\n"
        if len(line.encode()) > MAX_LINE_BYTES:
            raise ValueError("Policy request exceeds protocol limit")
        if self.stdin is None:
            raise RuntimeError("No worker stdin")
        self.stdin.write(line)
        self.stdin.flush()

    def close(self):
        if self.closed:
            return
        self.closed = True
        for sig, timeout in ((signal.SIGTERM, 5), (signal.SIGKILL, 2)):
            try:
                os.killpg(self.process.pid, sig)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=timeout)
                break
            except subprocess.TimeoutExpired:
                continue
        # uv may exit before its child; reap any remaining group members too.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.thread.join(timeout=1)
        if self.stdin is not None:
            try:
                self.stdin.close()
            except BrokenPipeError:
                pass
        if self.stdout is not None:
            self.stdout.close()
