"""Reproducible local microbenchmarks; no ROS, network, inference or robot I/O.

Run with Catbot's root uv Python and PYTHONPATH containing catbot_policy and
Orin's catbot_sim. Optional --baseline-directory loads saved recording_before.py
and ground_before.py for a same-process, same-input comparison.
"""

import argparse
import importlib.util
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from catbot_sim import ground

from catbot_policy import recording


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(callback, count):
    for _ in range(50):
        callback()
    samples = []
    for _ in range(count):
        start = time.perf_counter_ns()
        callback()
        samples.append((time.perf_counter_ns() - start) / 1000)
    return {
        "median_us": statistics.median(samples),
        "p95_us": sorted(samples)[int(count * 0.95)],
    }


def benchmark(rec, floor):
    with tempfile.TemporaryDirectory() as root, patch("threading.Thread.start"):
        journal = rec.SourceJournal(root, {})
        payload = {"stamp": {"sec": 1, "nanosec": 2}, "values": [0.123456789] * 90}

        def submit():
            journal.submit("feedback", payload)
            journal.queue.get_nowait()

        capture = measure(submit, 10000)
    header = SimpleNamespace(frame_id="optical")
    image = SimpleNamespace(
        width=128,
        height=128,
        step=512,
        encoding="32FC1",
        is_bigendian=False,
        header=header,
        data=np.full((128, 128), 0.4, dtype="<f4").tobytes(),
    )
    info = SimpleNamespace(
        width=128,
        height=128,
        header=header,
        p=[100.0, 0.0, 64.0, 0.0, 0.0, 100.0, 64.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    )
    fit = measure(
        lambda: floor.ground_reference(
            image, info, [0, 1, 0, 0], [0, 0, 0], [0, 0, 0], gravity_up=[0, 0, 1]
        ),
        200,
    )
    return {"source_submit": capture, "gravity_floor_fit": fit}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--baseline-directory", type=Path)
    args = parser.parse_args()
    result = {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "capture_samples": 10000,
            "floor_samples": 200,
            "warmup": 50,
        }
    }
    if args.baseline_directory:
        result["before"] = benchmark(
            load(args.baseline_directory / "recording_before.py"),
            load(args.baseline_directory / "ground_before.py"),
        )
    result["after"] = benchmark(recording, ground)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
