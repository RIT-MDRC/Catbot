# Validation of the local supervisor changes

Checked 2026-11-18 against the supervisor change and reviewed test cleanup. No
robot hardware or policy artifact was deployed. The Catbot base was `82d0844`,
training HEAD `d5b00fd`, and Orin HEAD `58281a0`. Tests use controlled mapping and
calibration inputs, retain the shared golden contract, and verify asynchronous
failures and emergency preemption without depending on mutable deployment defaults.

| Check | Result |
| --- | --- |
| Root Foundation/UI/supervisor suite in Policy CI | 162 passed |
| Full non-ROS policy suite | 62 passed |
| Policy coverage | runtime 94.35% >= 92%; deployment 93.44% >= 90% |
| New ROS policy/supervisor tests in Humble / Python 3.10 | 2 passed; generated interfaces and Foundation/policy/supervisor packages built |
| Affected runtime files: Ruff and ty | Passed; launch entry points also inspected using installed ROS `--show-args` |
| CLI tests | 2 passed |
| npm package dry run | Includes supervisor launch/runtime and generated `.msg`/`.srv` sources |
| Cross-project CPU compatibility skill | Training export, both Catbot runtime/export consumers, rejection checks, and Orin inverse/atomic mapping passed |
| Disposable Orin tree with updated Catbot sources | 187 non-ROS tests passed; every existing per-module coverage floor passed |
| Original downstream Orin ROS scenario/diagnostics tests | Both hit an existing test expression error: `bytes([DiagnosticStatus.OK])` / `bytes([level])` when Humble exposes those constants as bytes |
| Disposable downstream ROS test copy with portable byte comparisons | Both passed against the updated installed Catbot packages; Orin repository tests were not changed |

The new supervisor ROS test starts both real supervisor adapters and an actual
managed policy adapter process with a fake inference worker. It doubles hardware
and Linux health readings, then exercises boot, sequential calibration/arming,
ready with no forwarding, running, action acknowledgements, stale feedback,
emergency IDLE, explicit recovery, and shutdown/process cleanup. Pure tests cover
reordered/duplicate/gapped/stale actions, bad clocks/data, session changes,
heartbeat/probe loss, RTT/jitter, registry extension, service failures/timeouts,
process escalation/reaping, raw health sampling, and atomic motor-command
validation before I/O. Foundation's encoder validity rejects non-finite and
future/stale readings without doing kinematic conversion just to check readiness.

The compatibility skill checked Orin's actual pinned Catbot copy separately.
Combined downstream tests used `/tmp/catbot-supervisor-consumer`, a disposable
copy of Orin sources and the updated Catbot tree. The real Orin submodule pin
`2550241` and its pre-existing policy-deployment edits were preserved. Neither a
passing disposable tree nor the skill changes that deployment pin. Unmodified
Orin ROS CI still needs its diagnostic byte-constant test fix.

Not established: physical startup/calibration/emergency behavior, watchdogs after
Pi death, synchronized clocks/network jitter under robot load, actual Pi CPU
headroom/temperature versus the reported historical ~50%-one-core policy-only
baseline, CUDA parity, and deployment of these packages into Orin's pinned tree.
Use the README's recording command for the required on-Pi headroom capture.
