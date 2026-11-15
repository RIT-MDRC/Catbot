#!/usr/bin/env python3
"""Stdlib-only adversarial worker; accepts uv-style arguments for launch tests."""

import json
import os
import signal
import sys
import time
from pathlib import Path

mode = os.environ.get("FAKE_WORKER_MODE", "ready")
if mode == "timeout":
    time.sleep(60)
if mode == "ignore_term":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode in ("malformed", "oversized", "version", "array"):
    print(
        {
            "malformed": "{",
            "oversized": "x" * 131073,
            "version": '{"version": 999, "type": "ready"}',
            "array": "[]",
        }[mode],
        flush=True,
    )
    time.sleep(60)
else:
    fixture = json.loads(Path(__file__).with_name("contract.json").read_text())
    rollout = "catbot_rollout.worker" in sys.argv
    ready = (
        fixture["rollout"]
        if rollout
        else {
            "version": 1,
            "type": "ready",
            "metadata": fixture["metadata"],
            "mapping": fixture["mapping"],
            "dt": 0.02,
            "python_version": sys.version,
            "device": "cpu",
        }
    )
    print(json.dumps(ready), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        if rollout:
            response = {"feedback": fixture["feedback"]}
        elif request.get("type") == "step":
            response = {
                "version": 1,
                "type": "action",
                "id": request["id"],
                "actuator_names": fixture["mapping"]["actuator_names"],
                "positions_degrees": fixture["degrees"],
                "inference_seconds": 0.001,
            }
        elif request.get("type") == "ack":
            response = {
                "version": 1,
                "type": "done",
                "id": request["id"],
                "published": request["published"],
            }
        else:
            response = {"version": 1, "type": "echo", "request": request}
        print(json.dumps(response), flush=True)
