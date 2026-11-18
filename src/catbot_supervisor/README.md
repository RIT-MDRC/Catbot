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
`wait_state`, `wait_clear`, `wait_ready`, `wait_link`, `wait_health`, and
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
