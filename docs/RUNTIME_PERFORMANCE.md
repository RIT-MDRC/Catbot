# Runtime verification and extension guide

## Scope and reproducibility

The recording path separates capture (freeze values and capture source clocks),
transport (bounded single-producer queue), and persistence (writer thread).
`SessionRecorder.append_encoded` is the persistence boundary; additional capture
sources can reuse it without encoding the event again. `SourceJournal.status()`
and `/policy/recording/status` expose accepted records, writes, queue capacity,
depth, high-water mark, drops, writer liveness and errors. Queue depths are sampled
concurrently and are observational, not synchronization primitives.

Shutdown signals the writer and waits at most five seconds. A stuck filesystem
may leave a daemon writer alive until process exit; the session is incomplete
until it finishes. No producer waits for disk I/O or free queue capacity. Producer
serialization still costs CPU; a full queue skips it. Source timestamps precede
queue residence. Segment flush/fsync behavior remains unchanged.

Run the microbenchmark from the workspace parent with the locked policy-test
Python (NumPy is required), after preparing saved baseline modules:

```sh
mkdir -p /tmp/catbot-baseline
git -C catbot show cfa7ada:src/catbot_policy/catbot_policy/recording.py > /tmp/catbot-baseline/recording_before.py
git -C catbot-orin show d99a915:src/catbot_sim/catbot_sim/ground.py > /tmp/catbot-baseline/ground_before.py
PYTHONPATH=catbot/src/catbot_policy:catbot-orin/src/catbot_sim \
  catbot/tests/.venv/bin/python catbot/tools/benchmark_runtime_io.py \
  --baseline-directory /tmp/catbot-baseline
```

Measured on macOS arm64, Python 3.14.2, NumPy 2.5.4, with 50 warmups:

| Operation | Samples | Before median | After median | Before p95 | After p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Submit 90-value source feedback | 10,000 | 27.583 us | 20.959 us | 81.125 us | 22.041 us |
| Gravity-constrained 128x128 floor fit | 200 | 2897.292 us | 94.417 us | 3113.667 us | 104.375 us |

Capture timings include freezing/encoding and enqueueing, excluding file I/O.
Floor timings include depth projection, robust offset, residual/confidence and
broad-patch checks. The unconstrained calibration fit still uses RANSAC. These
are synthetic local samples, not end-to-end or Pi/Orin deadlines. Scheduling,
thermal state, NumPy build, payload shape and depth quality affect results;
performance thresholds are intentionally not enforced in unit tests.

## Extension priorities

- Measure end-to-end feedback-to-gate latency and CPU headroom on Pi/Orin under
  sensor, recording and Foxglove load before changing deadlines.
- Add DDS loss statistics separately from application queue overwrites. Never
  interpret the latter as a network-loss count.
- Extend the replay reader with schema/version validation, incomplete-line
  recovery and source/gate acknowledgement matching before automated sim replay.
- Introduce a dedicated capture process if filesystem/GIL contention measurably
  affects policy timing; preserve source clocks and bounded queues across IPC.
- Keep live shadow simulation disabled until a recorded A/B test demonstrates
  unchanged action/link latency. Add divergence thresholds only after establishing
  model, clock and frame consistency.
- Tune floor confidence/filter settings using recorded occlusion and motion
  sequences; retain finite-value, broad-patch and jump-rejection checks.

Unit regressions cover writer stalls, frozen payloads, source timestamps, queue
losses, and invalid ground quality. ROS integration exercises actual adapters
and serialization. Neither proves physical frame calibration, clock sync, CUDA,
CAN delivery, or useful learned motion.
