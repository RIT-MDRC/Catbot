# Pi launch and hardware configuration

Launch settings are owned by the node that consumes them. Foundation freshness
checks, Pi state-stream freshness, and Orin policy feedback freshness are separate
settings even when their default values happen to match. No policy observation,
action, gain, mapping, or hardware default is changed by this configuration support.

On the Pi, use the existing environment and launch with explicit test overrides:

```bash
ros2 launch catbot_supervisor rpi.launch.py \
  heartbeat_timeout_seconds:=1.0 encoder_timeout_seconds:=0.5
```

When Orin starts the Pi remotely, use the corresponding `rpi_` prefix:

```bash
ros2 launch catbot_launcher physical_orin.launch.py \
  rpi_heartbeat_timeout_seconds:=1.0 rpi_encoder_timeout_seconds:=0.5
```

`catbot_policy catbot.launch.py` also forwards these hardware launch arguments.
Run `ros2 launch catbot_supervisor rpi.launch.py --show-args` for the complete
list. Values are seconds unless their names specify another unit. Operational
values must be finite and positive; CPU headroom cannot exceed 100 percent.
Settings are startup-only and read-only as ROS parameters (the existing manual
control drag-timeout parameter retains its runtime update behavior where present).
Restart the hardware launch to apply changes; omit overrides to restore defaults.
Changing a freshness budget accepts older state; it does not remove a receive backlog.

## Foundation settings

Foundation checks both heartbeat and encoder freshness before reporting ready and
before sending motion commands. Both layers use the same configured budgets.
The motor arm timeout is separate: it bounds the pending idle-to-closed-loop transition.

| Launch argument | Default |
| --- | ---: |
| `heartbeat_timeout_seconds` | 0.5 |
| `encoder_timeout_seconds` | 0.25 |
| `motor_arm_timeout_seconds` | 0.5 |
| `position_state_period_seconds` | 0.02 |
| `state_check_period_seconds` | 0.05 |
| `error_request_period_seconds` | 1.0 |
| `gain_update_period_seconds` | 0.1 |
| `gain_scale_step` | 0.05 |
| `limits_publish_period_seconds` | 1.0 |

## Pi supervisor settings

The existing `action_age`, `heartbeat_age`, `max_rtt`, `max_jitter`, and
`future_tolerance` arguments configure the Orin action/link gate. `body_timeout`
(default 0.5) bounds receipt of complete Foundation state, not the age of an
individual motor heartbeat. `heartbeat_recovery_seconds` (1.0) requires stable
healthy feedback before automatic communication-fault recovery. Recovery never
restarts motion automatically.

Other existing launch settings are `min_cpu_headroom_percent` (10),
`max_temperature_c` (80), `controller_reconnect_timeout` (10), `network_interface`
(`eth0`), and `foundation_pid` (0 means discover the process). Where manual control
is available, `manual_drag_timeout` retains its existing 0.5-second default.
Gate defaults come from the node's `Limits` definition. The added operational
settings below retain their previous budgets. Built-in script overrides do not
replace plugin-owned script deadlines.

| Launch argument | Default |
| --- | ---: |
| `tick_period_seconds` | 0.02 |
| `probe_period_seconds` | 0.1 |
| `health_period_seconds` | 1.0 |
| `recovery_timeout_seconds` | 3.0 |
| `emergency_retry_seconds` | 1.0 |
| `remote_stop_retry_seconds` | 1.0 |
| `compute_warning_interval_seconds` | 30.0 |
| `shutdown_timeout_seconds` | 3.0 |
| `position_tolerance_degrees` | 1.0 |
| `velocity_tolerance_degrees_s` | 1.0 |
| `script_step_timeout_seconds` | 3.0 |
| `clear_errors_timeout_seconds` | 3.0 |
| `state_transition_timeout_seconds` | 3.0 |
| `arm_timeout_seconds` | 3.0 |
| `zero_ready_timeout_seconds` | 5.0 |
| `position_move_timeout_seconds` | 15.0 |
| `homing_timeout_seconds` | 30.0 |
| `calibration_timeout_seconds` | 60.0 |
| `operator_timeout_seconds` | 120.0 |
| `homing_delay_seconds` | 15.0 |
| `policy_startup_timeout_seconds` | 120.0 |
| `policy_stop_timeout_seconds` | 8.0 |
| `health_wait_timeout_seconds` | 5.0 |
| `job_restart_timeout_seconds` | 8.0 |
| `front_flexion_clearance_degrees` | 30.0 |

## Hardware and protocol files

`hardware_config_file:=/absolute/path/pinconfig.json` selects Foundation's existing
hardware file. It owns CAN bus settings, actuator-to-axis IDs, controller board
groups, motion profiles, linkage geometry and raw controller modes. The Pi launch
reads that same file to supply the supervisor's axis and controller-group roster;
there is no second hand-maintained CAN-ID list.

Each motor can specify `controller_reboot_axis`, the axis on its physical
controller board used to send a board reboot. Every axis on the same board uses
the same representative. The packaged file records the existing six board pairs
explicitly. Older files without the field retain adjacent-pair behavior.

`protocol_config_file:=/absolute/path/hardware_protocol.json` selects the shared
firmware protocol data. Its default is Foundation's packaged
`foundation/hardware_protocol.json`. It contains motor states, control/input mode
numbers, CAN command-ID layout, heartbeat command ID and the DBC file location.
Relative DBC paths resolve beside this protocol file. Foundation and the Pi
supervisor load the same protocol before initializing their nodes; Orin's node
settings remain independent. Direct Python/ROS-node users can select the protocol
with `CATBOT_PROTOCOL_CONFIG` before importing Foundation or the supervisor.

The protocol values must match the motor-controller firmware and the selected DBC.
The DBC owns CAN message schemas, command IDs and decoded error fields; existing
ODrive error enums keep their current public imports. Protocol changes require a
full hardware-launch restart. No firmware is modified by editing these files.
