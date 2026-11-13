"""ROS-free policy runtime on Python 3.14; one inference and acknowledgement at a time."""

import argparse
import contextlib
import json
import math
import os
import resource
import select
import sys
import time
from pathlib import Path

from catbot_policy.protocol import MAX_LINE_BYTES, VERSION, validate_feedback


class Discarded(Exception):
    """The host did not publish this result; leave action history unchanged."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--feedback-timeout", type=float, default=0.25)
    parser.add_argument("--ack-timeout", type=float, default=2.0)
    args = parser.parse_args()
    if not math.isfinite(args.ack_timeout) or args.ack_timeout <= 0:
        parser.error("--ack-timeout must be finite and positive")
    output = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

    def send(message):
        line = json.dumps({"version": VERSION, **message}, allow_nan=False) + "\n"
        if len(line.encode()) > MAX_LINE_BYTES:
            raise ValueError("Policy response exceeds protocol limit")
        output.write(line)
        output.flush()

    def read():
        line = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
        if not line:
            raise EOFError("ROS host disconnected")
        if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
            raise ValueError("Invalid or oversized policy request")
        value = json.loads(line)
        if not isinstance(value, dict) or value.get("version") != VERSION:
            raise ValueError("Unsupported policy protocol")
        return value

    with contextlib.redirect_stdout(sys.stderr):
        # Import PyTorch only after diagnostics are isolated from protocol stdout.
        from catbot_policy.runtime import PolicyRuntime

        runtime = PolicyRuntime(
            args.bundle.expanduser(),
            args.mapping.expanduser() if args.mapping else None,
            args.feedback_timeout,
        )
        send(
            {
                "type": "ready",
                "dt": runtime.dt,
                "metadata": runtime.metadata,
                "mapping": runtime.mapping.metadata,
                "python_version": sys.version.split()[0],
            }
        )
        while True:
            try:
                request = read()
            except EOFError:
                return
            if request.get("type") != "step":
                raise ValueError("Expected a step request")
            identity = request["id"]
            received = float(request["feedback_received"])
            now = time.monotonic()
            if (
                not math.isfinite(received)
                or not 0 <= now - received <= runtime.feedback_timeout
            ):
                send({"type": "done", "id": identity, "published": False})
                continue
            runtime.update_feedback(validate_feedback(request["feedback"]), received)
            runtime.set_command(request["command"])
            started = time.monotonic()

            def propose(names, targets, identity=identity):
                send(
                    {
                        "type": "action",
                        "id": identity,
                        "actuator_names": names,
                        "positions_degrees": targets,
                        "inference_seconds": runtime.last_inference_seconds,
                    }
                )
                readable, _, _ = select.select(
                    [sys.stdin.buffer], [], [], args.ack_timeout
                )
                if not readable:
                    raise TimeoutError("ROS publication acknowledgement timed out")
                acknowledgement = read()
                if (
                    acknowledgement.get("type") != "ack"
                    or acknowledgement.get("id") != identity
                ):
                    raise ValueError("Invalid publication acknowledgement")
                if acknowledgement.get("published") is not True:
                    raise Discarded()

            try:
                published = runtime.step(time.monotonic(), propose)
            except Discarded:
                published = False
            send(
                {
                    "type": "done",
                    "id": identity,
                    "published": published,
                    "worker_seconds": time.monotonic() - started,
                    "cpu_seconds": time.process_time(),
                    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                }
            )


if __name__ == "__main__":
    main()
