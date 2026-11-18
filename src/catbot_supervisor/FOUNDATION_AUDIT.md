# Foundation responsibility audit

Audited runtime: `foundation/main.py`, body helpers, component I/O,
`foundation/simulation.py`, policy adapter and launch entry point.

| Responsibility | Previous implementation | Result |
| --- | --- | --- |
| Automated startup | Clear every motor fault on construction; queue calibration after heartbeat discovery | Removed from Foundation; Pi boot only disarms, explicit startup script clears/calibrates |
| Maintenance scripts | `MotorSequence`, script-topic handlers, control timer, serial calibration/homing, automatic re-arm | Moved to Pi `scripts.py` registry/runner using immediate `MotorCommand` I/O |
| Robot modes/link verdict/action freshness | Direct policy-to-body publication, no Pi verdict | Pi `core.py`/`node.py`; sequences, timestamps, probe RTT/jitter, watchdogs and latched emergency |
| Emergency/shutdown sequencing | Foundation owns motor sequencing; low-level process exit disarms/closes CAN | Pi scripts own ordered actions and Orin requests. Foundation retains only resource cleanup and last-chance IDLE on its own exit |
| Policy lifecycle/inference | Separate policy package, legacy combined launch could start it on Pi | Hardware launch starts Pi supervisor; Orin Supervisor services own policy worker process lifetime |
| Policy telemetry/job execution | Policy adapter owns metrics and worker; no Foundation job runner found | Policy metrics stay with the Orin-hosted policy job; additional jobs are allowlisted behind Orin services |
| Body telemetry | Fresh encoder/heartbeat/error flags and CAN detailed-error requests | Retained as core Foundation sensor/body I/O; periodic body state lets Pi detect a dead Foundation |
| Actuation safety | Sparse atomic target validation, logical/profile conversion, faults, closed-loop checks | Retained; direct motor operations validate the whole named batch before sending |
| Manual hardware tools | Explicitly invoked standalone `samples/` programs | Retained as manual test tools; no runtime import, registry, startup hook, or job path executes them |
| Simulation | Mapping validation and transport | Retained; no hardware initialization or robot script execution |

Foundation's remaining runtime timers publish body position/state and request raw
CAN fault details. It neither waits for motor transitions nor clears faults,
calibrates, homes, arms, starts policy, or launches a process automatically. Its
motor service performs one explicitly requested operation and returns send status;
the supervisor owns sequencing and confirmation. The existing script topics were
removed, rather than retained as hidden orchestration aliases.
