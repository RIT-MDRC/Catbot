# Catbot supervisors

The Pi owns robot decisions and scripted body operations. Orin owns inference,
policy metrics, and managed jobs. Foundation provides immediate body I/O.

```text
Orin policy -> stamped PolicyAction -> RPi Supervisor -> Foundation position I/O
    ^                                      |
    +---------- Pi forwarding ack ---------+
Orin Supervisor -> heartbeat/probe echo -> Pi link verdict
RPi scripts -> Foundation MotorCommand + Orin SupervisorJob services
```

Policy history advances only when the Pi acknowledges forwarding. Rejected
proposals leave history unchanged. The acknowledgement means publication to
Foundation, not physical execution; Foundation independently validates bounds,
axis faults, fresh encoders/heartbeats, and closed-loop state.

## Build and launch

Build the same Catbot revision on each machine with ROS Humble's Python ABI.
Inference remains in its existing isolated CPU/CUDA environment. Configure the
same ROS domain/network and synchronized ROS clocks on both machines (for example,
chrony). Cross-machine action age uses the ROS clock; RTT/jitter and watchdogs use
Pi monotonic time and do not require synchronized clocks. Clock skew beyond the
future tolerance or age budget closes the gate.

```bash
colcon build --packages-select catbot_interfaces catbot_policy foundation catbot_supervisor
source install/setup.bash

# On Pi: Foundation + RPi Supervisor; no policy worker.
ros2 launch catbot_supervisor rpi.launch.py network_interface:=eth0

# On Orin: service host only; startup requests the policy through its API.
ros2 launch catbot_supervisor orin.launch.py policy_bundle:=/absolute/path/to/bundle policy_device:=cuda:0
```

Keep the existing Orin sensors/kinematics feedback provider running. It must use
the same policy/model/mapping contract. `mapping_file` selects the Pi's complete
actuator roster; Orin's mapping must agree. `foundation_pid:=123` can override
Linux `/proc` process discovery if multiple Foundation instances exist.

`ros2 launch catbot_policy catbot.launch.py` now delegates its hardware backend to
the Pi launch. Its simulation backend retains the existing local policy path.
Hardware policy output requires the session assigned by Orin Supervisor. Direct
hardware policy launch is no longer supported. `catbot start` still starts only
Foundation, which now remains disarmed until explicitly commanded.

The sibling `catbot-orin` consumes its own pinned `external/Catbot` checkout.
These changes do not update that pin or its legacy physical scenario launchers.
Deploy the updated packages and use these supervisor launches together; stop any
legacy direct-policy/physical scenario launch before starting them. Simulation
consumers and the existing body position message are unchanged.

## Modes and operator API

Boot requests IDLE for the complete configured roster, then confirms it before
entering idle. Nothing automatically calibrates or arms at process startup.

```bash
# Explicit startup includes sequential calibration and can move hardware.
ros2 service call /rpi/supervisor/script catbot_interfaces/srv/RunScript "{name: startup}"
ros2 topic echo /rpi/supervisor/status std_msgs/msg/String
# Wait for ready, then enable forwarding:
ros2 service call /rpi/supervisor/run std_srvs/srv/Trigger '{}'
# Pause forwarding, holding the last target in ready mode:
ros2 service call /rpi/supervisor/idle std_srvs/srv/Trigger '{}'
# Disarm immediately through the emergency script:
ros2 service call /rpi/supervisor/emergency std_srvs/srv/Trigger '{}'
# Recovery requires confirmed idle axes. It does not restart motion.
ros2 service call /rpi/supervisor/recover std_srvs/srv/Trigger '{}'
ros2 service call /rpi/supervisor/script catbot_interfaces/srv/RunScript "{name: shutdown}"
```

| Mode | Behavior |
| --- | --- |
| boot | Disarm at boot, or execute an explicitly requested startup/maintenance script; gate closed |
| idle | Disarmed, awaiting an explicit script |
| ready | Healthy link/body/Pi, axes armed; proposals checked, forwarding paused |
| holding | Local homing complete, axes armed; Pi/body checks active, policy forwarding disabled, no Orin required |
| running | Only fresh, consecutive actions for the current session and complete roster are forwarded |
| degraded | Pi link verdict immediately transitions to latched emergency |
| emergency | Gate closed; IDLE all axes and request Orin policy stop; retry local disarm until confirmed |
| shutdown | Gate closed; disarm and stop policy; terminal until node restart |

Unsafe action timestamps, duplicates/reordering/gaps, session changes, missing
heartbeats/probe echoes, excessive RTT/jitter, an Orin degraded report, stale body
state, axis unavailability, or unhealthy Pi readings trigger emergency in ready
or running. No automatic recovery resumes motion. A link failure during an active
linked script also aborts into emergency. Shutdown preempts a pending script.
Orin stops all registered jobs if its Pi probe lease expires.

Defaults: 250 ms action age, 500 ms heartbeat/probe/body age, 150 ms RTT, 50 ms
jitter, 20 ms future-clock tolerance, 10% aggregate idle CPU headroom, 80 C Pi
temperature. ROS parameters on the nodes configure these thresholds. Jitter is an
EWMA (alpha 0.2) of successive RTT differences. Heartbeats carry their own sequence
and latest action sequence; status reports both alongside the accepted sequence.
Probe echoes are matched to outstanding Pi requests and consumed once.

## Script registry and Orin services

Built-ins are `startup`, `shutdown`, `emergency`, `home`, `calibrate`,
`full_calibrate`, and `clear_errors`. Maintenance explicitly disarms, clears faults,
waits for each motor operation, configures trajectory, holds measured position,
then requests and confirms closed loop per axis. Service success means the
request was sent; scripts wait for body-state confirmation before advancing.

Install a Python entry point under `catbot_supervisor.scripts` to add a script
without editing the node. The factory receives the complete actuator-name tuple
and returns `Step` objects from `catbot_supervisor.scripts`. Existing script names
cannot be overridden. Supported steps are `motor`, `job_start`, `job_stop`,
`wait_state`, `wait_cycle`, `wait_clear`, `wait_ready`, `wait_link`, `wait_health`, and
`wait_policy_stopped`. Startup waits for previous policy cleanup; shutdown waits
for the Orin heartbeat to confirm that the policy process group was reaped.
Every step has a timeout. An emergency replaces the active runner without waiting
for a pending remote response. Custom scripts run under the same closed gate and
local health/link checks as maintenance scripts.

Orin's `/orin/supervisor/job` (`SupervisorJob`: `name`, `start`) starts/stops only
registered commands. `policy` is reserved and constructed from policy parameters;
its child gets a new session on each restart. Add recording or telemetry jobs with
`jobs_json`, a JSON object mapping names to argv arrays. There is no arbitrary
command field in the service. Launch accepts `jobs_json` as a string. For example:

```bash
ros2 launch catbot_supervisor orin.launch.py \
  policy_bundle:=/absolute/path/to/bundle \
  'jobs_json:={"record":["ros2","bag","record","/policy/metrics"]}'
ros2 service call /orin/supervisor/job catbot_interfaces/srv/SupervisorJob "{name: record, start: true}"
```

The Orin service uses process groups, bounded SIGINT/SIGTERM/SIGKILL escalation,
and child reaping. Its periodic heartbeat reports degraded policy/job state and
raw probe/action sequence facts. It never selects a robot mode or judges the Pi
link. Foundation has no worker, job registry, script registry, or policy imports.

## Pi measurement and remaining hardware checks

`/rpi/supervisor/status` includes one-second Linux `/proc` samples for aggregate
CPU headroom and Foundation process CPU (100% means one core), NIC operstate, and
Pi thermal-zone temperature. The first CPU sample is unknown until two counters
exist. Missing telemetry is reported as unknown and prevents ready/running.
Foundation process restarts reset the CPU delta. Record status while the policy
runs on Orin with Foundation, sensors, and network traffic under representative
load:

```bash
ros2 topic echo /rpi/supervisor/status std_msgs/msg/String > /tmp/pi-supervisor-health.yaml
```

The reported policy-only baseline is approximately 50% of one Pi core without
Foundation, supplied in the task. It is labeled as a reported historical baseline,
not a new measurement. Compare Foundation's measured process CPU and the Pi's
aggregate idle headroom under the combined workload; retain the raw capture and
its duration. These software tests do not prove CPU headroom improvement or
validate physical calibration, emergency motion, temperature, SSH, or CUDA.

ROS/DDS publisher identity is not an access-control boundary. Provision the
robot's ROS permissions so Orin cannot publish directly to Foundation command
endpoints or forge Pi acknowledgements. A Pi process/OS crash also needs the
motor/controller watchdog or an independent hardware stop: a software script
cannot execute after the Pi has died.

## Orin service contract (status JSON version 1)

The watchdog remains fail-latched. There is no automatic policy restart. A stale
250 ms action stream is reported as degraded; the Pi owns sequence verdicts and
emergency/recovery. Losing the Pi's probes for 500 ms cancels queued restarts and
stops every registered job.

`SupervisorJob` keeps the legacy `name` + `start` fields. Its new `operation`
field accepts `start`, `stop`, or `restart`; empty uses the legacy bool. Restart
queues one replacement behind bounded process-group cleanup. Repeated requests
coalesce, stop cancels a replacement, and preflight/lease are rechecked before
spawning. Requests report acceptance; they do not claim that cleanup/load ended.

```bash
ros2 service call /orin/supervisor/job catbot_interfaces/srv/SupervisorJob "{name: policy, operation: restart}"
ros2 service call /orin/supervisor/get_status catbot_interfaces/srv/GetSupervisorStatus "{name: policy}"
# Preferred robot restart path: closes the gate, disarms, restarts and re-arms;
# explicit /rpi/supervisor/run is still required afterwards.
ros2 service call /rpi/supervisor/script catbot_interfaces/srv/RunScript "{name: restart_policy}"
```

`GetSupervisorStatus` accepts an empty name for all jobs. `status_json` contains:
`version: 1`, `jobs` (state, PID, exit code, error), `policy` (session, ready,
verified, bundle_id, load_error), `preflight` (passed/reason), `clock` (offset,
uncertainty/reason), `tags`, and `resources`. Unknown job names fail explicitly.
States are stopped, running, stopping, restarting, and failed. Loading/verified
readiness is reported separately from the job's process existence.

A policy worker reports verified only after metadata/checksum validation and
actor loading. Bundle ID is the SHA-256 of the serialized policy actor, distinct
from the physical model hash. `PolicyReady` is tied to the current process session;
old readiness cannot arm a replacement. The managed policy also waits for a
matching `/policy/contract` from the feedback bridge, including model hash,
policy contract, settings and mapping. Hardware and simulation both use this check;
supervised action routing is independent of simulation mode.

Before policy start, the Pi startup script waits for the Orin preflight verdict.
Orin publishes `ClockProbe` and Pi returns `ClockReply` with receive/send times.
Orin computes the four-timestamp offset and half-RTT uncertainty bound, rejects
replays, delayed replies and local clock steps, and requires
`abs(offset) + uncertainty <= clock_tolerance` (20 ms default). Estimates expire
after two seconds. Orin also requires known temperature below 80 C, at least 1 GiB
free disk, and a successful bounded compute allocation probe in the selected
CPU/CUDA inference environment. The ROS interpreter never imports PyTorch.
Preflight failure is visible in the heartbeat and get_status; it blocks starts
and replacements. A failed compute probe requires repairing/restarting the Orin
host; it is not automatically retried during robot operation.

`/orin/supervisor/telemetry` is typed `OrinTelemetry`, published at 1 Hz: aggregate
CPU use, Jetson sysfs GPU load where available, maximum exposed thermal-zone
temperature, memory used/total, disk free/total, run ID, git commit, scenario and
verified policy bundle ID. Unknown floating measurements are NaN, with validity
and GPU-availability flags; status JSON uses null. Missing temperature/memory/disk
facts fail preflight. A missing GPU load sensor is explicitly unavailable and
never treated as zero usage. Policy inference metrics remain `/policy/metrics`.
Run ID defaults to the selected policy run ID or a generated session tag; it can
be set using `supervisor_run_id`. Set `git_commit` explicitly if launching outside
a Git checkout. `disk_path`, resource sys/proc roots and thresholds are parameters.

Both hosts must rebuild/source the updated generated interfaces together. The Pi
retains its own launch/config; Orin deployment configuration belongs in the Orin
repository. Recording/rosbag coordination, capture rotation and offline/shadow
simulation scheduling remain deferred and are not implemented by these APIs.

## Clickable software e-stop in Foxglove

For homing and policy controls together, import
[foxglove/operator-controls.json](foxglove/operator-controls.json). It includes:

- **Home robot**: runs local `home_robot`; no policy or Orin supervisor required.
- **Motor calibration**: explicitly runs the existing motor calibration script.
  `calibrate` and `full_calibrate` run the complete sequence below. They can move
  hardware, clear faults, and finish with all motors armed/holding. `home_robot`
  remains the separate homing-only script and never clears faults.
- **Start policy (no motor commands)**: calls the Orin job service with
  `{"name":"policy","operation":"start"}`. It loads/starts inference only;
  it does not start any Pi script, arm motors or enable policy forwarding.
- **Stop policy — keep holding**: the Pi closes forwarding before requesting
  policy stop. Armed motors stay in local holding mode.
- **RUN — ENABLE POLICY MOTION**: explicitly enables forwarding from READY or
  local HOLDING, only with fresh healthy policy actions and ready body/Pi.
- **Pause policy motion — hold**: pauses forwarding but keeps motors armed.
- **E-STOP — DISARM**: aborts and disarms; also requests policy stop.
- A status/prompt panel, editable confirmation, Orin status query, and
  **Run named script** panel. `available_scripts` in Pi status lists built-ins
  and installed entry-point scripts; enter any registered name to start it.

Starting policy from Foxglove requires the Orin Supervisor and its normal
sensing/kinematics providers to be launched and healthy. A bridge-only launch
supports local homing but does not provide policy services or observations.
The CPU worker must match the selected training run's configuration before
using the physical scenario; the button cannot repair a failed provider.
The Pi `run` service retains all existing readiness/fresh-action checks.

### Full calibration and ordered homing

The Motor calibration button requests `calibrate`; `full_calibrate` is an alias
for the same robot sequence. It does not start policy or enable forwarding:

1. Disarm the complete roster, confirm IDLE, clear errors, and confirm clear.
2. Request controller FULL_CALIBRATION_SEQUENCE (state 3) for all 12 actuators
   in one batch, without waiting on individual motors. Track each actuator's
   calibration substates and require every actuator to return to fault-free IDLE
   before continuing (60-second timeout).
3. Home `flk, frk, blk, brk` together. Wait for the entire group to finish homing
   and return to IDLE, then configure trajectory, hold measured position, and arm
   each member, confirming closed-loop readiness before continuing.
4. Repeat that homing/completion/arming barrier for `flf, frf, blf, brf`.
5. Repeat it for `bla, bra`.
6. Command the already armed `flf, frf` to absolute logical **+30 degrees** and
   wait for valid, settled measured feedback (15-second timeout).
7. Pause for the operator's clearance confirmation. Use the current prompt ID
   from `/rpi/supervisor/status` with the layout's confirmation control. No front
   abduction homing is issued before that confirmation (120-second timeout).
8. Home `fla, fra` together, wait until both have finished and returned to IDLE,
   then arm/confirm them as above. Finish in local `holding`, with forwarding off.

Each homing group has a 30-second completion timeout. Faster axes cannot advance
the group barrier; each must be observed active and then IDLE. Arming is rejected
if any actuator is still homing. Pi health, fresh complete Foundation feedback,
and all reported fault fields remain checked during the sequence and operator
pause. Faults/timeouts preempt into latched emergency and IDLE the full roster.
Motor commands are sent over CAN individually within a batch; their controller
operations overlap rather than being serialized by per-axis completion waits.

ODrive 0.5.6 expands state 3 into individual calibration tasks rather than
reporting state 3 throughout; see its
[state machine](https://github.com/odriverobotics/ODrive/blob/fw-v0.5.6/Firmware/MotorControl/axis.cpp).
This software checks observed task activity, return to IDLE, faults and eventual
closed-loop readiness; it does not introduce a separate controller calibration
result message or prove physical calibration.

If the physical scenario's worker reports
`Catbot config must contain exactly the CatbotConfig settings`, stop that launch
and align the CPU rollout environment to the selected run's recorded training
revision. From the Orin workspace after sourcing its ROS overlay:

```bash
/usr/bin/python3 - <<'PY'
from pathlib import Path
from catbot_policy.rollout_setup import prepare_rollout
workspace = Path.cwd()
prepare_rollout(
    workspace / "external/catbot_sim_rollout",
    workspace / "external/Catbot/src/catbot_policy/artifacts/selected",
)
PY
```

Use the actual run directory if launching an explicit run instead of `selected`.
This existing helper pins/locks/syncs the simulator's `.venv` from the manifest,
then validates the saved config; it does not modify policy `.venv-cuda`. After it
succeeds, launch `catbot_launcher physical_orin.launch.py` with the correct
`workspace` argument to provide the Orin Supervisor and observations. Homing
alone needs only Foxglove Bridge and does not need this repair.

Import [foxglove/software-estop.json](foxglove/software-estop.json) using
Foxglove's **Layouts > Import from file**. It provides a red **E-STOP — DISARM**
button and a supervisor status panel. Both files use Foxglove's exported
`configById` / `layout` format, with `CallService` panel IDs. The programmatic
SDK's `version` / `content` format is not a layout-import file. After a colcon
build the files are also installed under
`$(ros2 pkg prefix catbot_supervisor)/share/catbot_supervisor/foxglove/`.

Connect to the robot's live Foxglove Bridge. Its `services` capability must be
enabled and its `service_whitelist` must permit `/rpi/supervisor/emergency`.
The bridge can run on either host if it can discover the Pi's ROS services.
No additional e-stop daemon is needed: this calls the existing Pi Supervisor
`std_srvs/srv/Trigger` service with `{}`. The button has no confirmation dialog.

To add the button to an existing layout (or on a Foxglove version that cannot
import this schema), add a **Service Call** panel with these settings:

| Setting | Value |
| --- | --- |
| Service name | `/rpi/supervisor/emergency` |
| Request | `{}` |
| Button title | `E-STOP — DISARM` |
| Button color | `#d32f2f` |
| Editing mode | Off, after entering the request |
| Timeout | 3 seconds |

Clicking latches Pi emergency mode, closes policy forwarding, replaces any
active script/operator prompt with the disarm sequence, and asynchronously
requests the Orin policy to stop. The Pi retries disarming until fresh body
feedback confirms all axes are IDLE. Service acceptance is not confirmation
that hardware has stopped: inspect `/rpi/supervisor/status` and
`/body/state/error` for mode, faults and actual axis state.

Recovery is a separate explicit `/rpi/supervisor/recover` Trigger call after
confirmed IDLE; it does not resume the interrupted script or motion. The layout
deliberately has no recovery/run button next to the e-stop.

This is a software disarm, not a power cut or a guaranteed physical stop. Motor
IDLE removes active holding torque, so support the robot. It requires a working
Foxglove/ROS connection, Pi process and motor communication; retain a physical
e-stop for failures of those components.

References: [Service Call panel](https://docs.foxglove.dev/docs/visualization/panels/service-call),
[layout import](https://docs.foxglove.dev/docs/visualization/layouts).
The JSON follows the shape of Foxglove's
[exported example layouts](https://github.com/foxglove/tutorials/blob/main/integrations/ros1/transforms/foxglove_layouts/Transforms.json).
Live Foxglove rendering and physical disarm still require target verification.

On Ctrl-C or launch SIGTERM, the Pi supervisor keeps ROS alive for a bounded
disarm attempt before destroying the node/context. Foundation independently
requests motor IDLE and closes CAN before shutting down its context. Repeated
termination signals are ignored during this bounded cleanup; SIGKILL still
cannot run cleanup. An externally invalidated ROS context is not used for
supervisor service calls.

## Robot homing sequence (`home_robot`)

Call `/rpi/supervisor/script` with `{"name":"home_robot"}` from Foxglove's
Service Call panel, or use:

```bash
ros2 service call /rpi/supervisor/script catbot_interfaces/srv/RunScript '{name: home_robot}'
```

The sequence is implemented in `catbot_supervisor/scripts.py:home_robot`:

0. Reject stale/missing actuator state, missing heartbeats, or any nonzero axis,
   motor, encoder, sensorless or controller error flags. Never clear errors.
1. Disarm all axes and confirm IDLE, then home knees: `flk`, `frk`, `blk`, `brk`.
2. Home flexion/extension: `flf`, `frf`, `blf`, `brf`.
3. Command `flf` and `frf` to absolute **+30 degrees** in Foundation's logical
   joint coordinates, using the configured trajectory profiles. Require fresh,
   valid post-command feedback within 1 degree, with speed at most 1 degree/s,
   before advancing (15-second timeout).
4. Prompt: confirm that the front legs are clear. Respond through
   `/rpi/supervisor/respond` with `{"name":"<current operator_prompt.id>"}`.
   The prompt appears in `/rpi/supervisor/status` and expires after 120 seconds.
5. Home abduction/adduction: `fla`, `fra`, `bla`, `bra`.

Each group runs one actuator at a time. For each axis, request homing (controller
state 11), observe homing then IDLE (30-second completion timeout), configure its
trajectory, hold measured position, request closed loop, and confirm readiness.
Each motor is armed immediately after its own homing finishes, before the next
motor starts. There is a 15-second buffer after each complete homing group,
after the front joints reach +30 degrees, and after operator confirmation before
abduction/adduction starts. These five buffers add 75 seconds to the sequence;
they are pauses after completion, not replacements for feedback checks or
operation timeouts. Fault/link/health checks and the e-stop remain active during
every buffer.
This keeps previously homed axes holding while later axes home. The front
flexion joints keep their +30-degree targets through the prompt and final group.
Successful completion leaves all axes in local `holding` mode, with policy
forwarding disabled. Starting policy through the Orin job service does not arm
or move anything. Once a verified policy produces fresh actions, an explicit
`run` request may transition from HOLDING to RUNNING after local/link checks.

The complete standard twelve-actuator roster is required; unknown/incomplete
rosters are rejected. Initial faults reject the request without starting the
sequence. During execution every tick checks all axes for faults, even while
waiting for the operator. A fault, stale state, Pi health failure, rejected
operation or timeout aborts to the latched emergency disarm path. Use the
Foxglove e-stop above to abort manually. There is no automatic retry or error
clearing. Inspect the fault reason in `/rpi/supervisor/status`.

This uses controller-configured homing/endstops and logical joint calibration;
it does not establish their physical correctness or write offsets. Pi health and
Foundation freshness/fault checks remain active. This script does not require an
Orin supervisor, policy worker, simulator or camera. Deploy/rebuild the Pi
package before use; local tests do not validate hardware travel or clearance.

For local homing, run `ros2 launch catbot_supervisor rpi.launch.py` on the Pi.
On Orin, source ROS and the workspace, then run only
`ros2 launch foxglove_bridge foxglove_bridge_launch.xml`. Both hosts must share
the ROS domain/discovery configuration. Connect Foxglove to `ws://<ORIN-IP>:8765`
and call `home_robot` as above. The physical scenario launcher is unnecessary
for this test and starts a kinematics worker that depends on saved policy files.

## Example: operator prompted homing/calibration from Foxglove

`sample_home` and `sample_calibrate` are editable examples in
`catbot_supervisor/scripts.py:prompted_maintenance`. They disarm and clear faults,
then ask for confirmation before each axis's controller operation. After all
operations, the existing maintenance sequence holds measured positions and arms
closed loop. Policy forwarding remains paused until an explicit `run` request.
They require healthy Pi/body telemetry but no Orin policy. Completion leaves
local holding mode; policy forwarding remains disabled until explicitly enabled.

`sample_home` requests ODrive state 11 (controller-configured homing).
`sample_calibrate` requests state 4 (motor calibration). Neither measures a joint
zero, writes encoder offsets, saves controller configuration, or verifies physical
homing/endstop setup. Adapt the procedure and prompts before hardware use.

1. Rebuild/source `catbot_supervisor` on the Pi and launch the supervisors as above.
2. Connect Foxglove through Foxglove Bridge with service calls enabled and the
   supervisor services permitted by its service whitelist.
3. Add a **Service Call** panel for `/rpi/supervisor/script`. Enter the JSON request
   `{"name":"sample_home"}` (or `{"name":"sample_calibrate"}`). Acceptance means
   the sequence started, not that calibration completed.
4. Add a **Raw Messages** panel for `/rpi/supervisor/status`. Expand the String
   message's JSON `data`; `operator_prompt` contains `id` and `text` while waiting.
5. After checking the requested setup, use another **Service Call** panel for
   `/rpi/supervisor/respond`, entering `{"name":"<current operator_prompt.id>"}`.
   Each ID works once for that prompt only. Early, duplicate, expired and replaced
   prompts are rejected. The next tick continues the script.
6. To abort, call `/rpi/supervisor/emergency` with `{}`. This preempts the prompt,
   closes the gate and requests IDLE. A 120-second unanswered prompt also fails
   into the existing latched emergency path. Existing link/health watchdogs remain
   active while waiting.

The same response works from a Pi terminal, without blocking a ROS callback:

```bash
ros2 service call /rpi/supervisor/script catbot_interfaces/srv/RunScript '{name: sample_home}'
ros2 topic echo /rpi/supervisor/status std_msgs/msg/String
# Copy the current prompt ID after checking the setup:
ros2 service call /rpi/supervisor/respond catbot_interfaces/srv/RunScript '{name: REPLACE_WITH_CURRENT_PROMPT_ID}'
```

This reuses `RunScript.name` as the response ID so no generated interface rebuild
is needed. Operator input currently supports confirmation; abort uses emergency.
For numerical offsets or multiple choices, add a dedicated typed response service
with prompt ID and validated values when the physical procedure is defined.
A future custom Foxglove panel can render prompt text and a Confirm button using
these same endpoints, avoiding manual ID copying. A terminal helper could likewise
use `input()` in its own process and call the response service afterwards.

Foxglove reference: [Service Call panel](https://docs.foxglove.dev/docs/visualization/panels/service-call).
