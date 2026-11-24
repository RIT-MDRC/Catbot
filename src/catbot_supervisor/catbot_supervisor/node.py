"""RPi Supervisor: sole policy-to-Foundation gateway and robot sequencer."""

import math
import signal
import time
from concurrent.futures import Future
from types import SimpleNamespace

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from rclpy.task import Future as RosFuture
from std_msgs.msg import UInt64
from std_srvs.srv import Trigger

from catbot_interfaces.msg import (
    ActuatorPositionCommand,
    BodyErrorState,
    BodyKinematicState,
    ClockProbe,
    ClockReply,
    OrinHeartbeat,
    PolicyAction,
    PolicyActionAck,
    SupervisorHealth,
    SupervisorOperatorPrompt,
    SupervisorStatus,
)
from catbot_interfaces.srv import (
    MotorCommand,
    RebootControllers,
    RunScript,
    SupervisorJob,
)
from catbot_supervisor.core import (
    ActionGate,
    Limits,
    Mode,
    status_bool,
    status_float,
    status_sequence,
    status_string,
    status_uint32,
)
from catbot_supervisor.health import PiHealth, compute_warning, health_reason
from catbot_supervisor.homing import (
    StateCycle,
    at_position,
    fault_reason,
    readiness_reason,
)
from catbot_supervisor.scripts import ScriptRunner, Step, registry


class RpiSupervisor(Node):
    def __init__(self):
        super().__init__("rpi_supervisor")

        def param(name, default):
            return self.declare_parameter(name, default).value

        self.gate = ActionGate(
            Limits(
                **{
                    name: float(param(name, value))
                    for name, value in vars(Limits()).items()
                }
            )
        )
        self.gate.probe_sequence = time.monotonic_ns()
        self.body_timeout = float(param("body_timeout", 0.5))
        self.min_headroom = float(param("min_cpu_headroom_percent", 10.0))
        self.max_temperature = float(param("max_temperature_c", 80.0))
        if (
            not all(
                math.isfinite(v) and v > 0
                for v in (self.body_timeout, self.min_headroom, self.max_temperature)
            )
            or self.min_headroom > 100
        ):
            raise ValueError("Invalid Pi health/body limits")
        self.names = tuple(param("actuator_names", [""]))
        if (
            not self.names
            or any(not n for n in self.names)
            or len(set(self.names)) != len(self.names)
        ):
            raise ValueError("Configure the complete unique actuator_names roster")
        self.health = PiHealth(
            str(param("network_interface", "eth0")), int(param("foundation_pid", 0))
        )
        self.health_sample = None
        self.body, self.body_at = {}, float("-inf")
        self.positions, self.positions_at = {}, float("-inf")
        self.script_position_at = float("inf")
        self.state_cycle = None
        self.scripts = registry()
        self.script_name = ""
        self.script_link_required = False
        self.orin_action_sequence = 0
        self.orin_policy_active = False
        self.orin_preflight_passed = False
        self.orin_policy_ready = False
        self.orin_policy_verified = False
        self.orin_bundle_id = ""
        self.remote_stop_at = float("-inf")
        self.emergency_attempt = float("-inf")
        self.hold_healthy = False
        self.recovery_generation = 0
        self.recovery_deadline = None
        self.motor = self.create_client(MotorCommand, "/body/control/motor")
        param("controller_reconnect_timeout", 10.0)
        self.reboot_wait = None
        self.reboot_since = {}
        self.reboot_client = self.create_client(
            RebootControllers, "/body/control/reboot_controllers"
        )
        self.create_service(
            RebootControllers,
            "/rpi/supervisor/reboot_controllers",
            self.reboot_controllers,
            callback_group=ReentrantCallbackGroup(),
        )
        self.jobs = self.create_client(SupervisorJob, "/orin/supervisor/job")
        self.output = self.create_publisher(
            ActuatorPositionCommand, "/body/control/position", 1
        )
        self.moves = self.create_publisher(
            ActuatorPositionCommand, "/body/control/move/position", 1
        )
        self.acks = self.create_publisher(
            PolicyActionAck, "/rpi/supervisor/action_ack", 1
        )
        self.clock_replies = self.create_publisher(
            ClockReply, "/rpi/supervisor/clock_reply", 1
        )
        self.create_subscription(
            ClockProbe, "/orin/supervisor/clock_probe", self.clock_probe, 1
        )
        self.probes = self.create_publisher(UInt64, "/orin/supervisor/probe", 1)
        self.status = self.create_publisher(
            SupervisorStatus,
            "/rpi/supervisor/status",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.runner = ScriptRunner(self.dispatch, self.satisfied)
        self.create_subscription(PolicyAction, "/orin/policy/action", self.action, 1)
        self.create_subscription(
            OrinHeartbeat, "/orin/supervisor/heartbeat", self.heartbeat, 1
        )
        self.create_subscription(
            BodyErrorState,
            "/body/state/error",
            self.body_state,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.create_service(RunScript, "/rpi/supervisor/script", self.run_script)
        self.create_subscription(
            BodyKinematicState,
            "/body/state/position",
            self.position_state,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        self.create_service(RunScript, "/rpi/supervisor/respond", self.respond)
        for name, callback in (
            ("run", self.run),
            ("idle", self.idle),
            ("emergency", self.emergency),
            ("recover", self.recover),
            ("policy_stop", self.policy_stop),
        ):
            self.create_service(Trigger, "/rpi/supervisor/" + name, callback)
        self.create_timer(0.02, self.tick)
        self.probe_timer = self.create_timer(0.1, self.probe)
        self.create_timer(1.0, self.sample_health)
        # Boot only disarms. Startup/calibration requires an explicit script request.
        self.script_name = "boot"
        self.runner.start([Step("motor", "idle"), Step("wait_state", state=1)])

    def body_state(self, message):
        names = [a.actuator_name for a in message.actuators]
        if len(names) != len(set(names)) or set(names) != set(self.names):
            self.enter_emergency("Foundation actuator roster mismatch")
            return
        self.body = {a.actuator_name: a for a in message.actuators}
        self.body_at = time.monotonic()
        if self.state_cycle is not None:
            self.state_cycle.observe(self.body)

    def body_fresh(self):
        return bool(self.body) and time.monotonic() - self.body_at <= self.body_timeout

    def position_state(self, message):
        names = [a.actuator_name for a in message.actuators]
        if len(names) != len(set(names)) or set(names) != set(self.names):
            self.positions, self.positions_at = {}, float("-inf")
            return
        self.positions = {a.actuator_name: a for a in message.actuators}
        self.positions_at = time.monotonic()

    def homing_fault(self):
        if self.health_sample is None:
            return "Pi health not sampled"
        reason = health_reason(
            self.health_sample, self.min_headroom, self.max_temperature
        )
        if reason:
            return reason
        if not self.body_fresh():
            return "Homing requires fresh Foundation state"
        return fault_reason(self.body, self.names)

    def local_script(self):
        return self.script_name not in (
            "",
            "boot",
            "emergency",
            "shutdown",
            "startup",
            "restart_policy",
        )

    def dispatch(self, step):
        if self.script_name in ("home_robot", "zero_all") or (
            self.script_name in ("calibrate", "full_calibrate")
            and self.state_cycle is not None
        ):
            reason = self.homing_fault()
            if reason:
                raise RuntimeError(reason)
        if step.kind in ("position", "position_armed"):
            if self.script_link_required and not self.gate.check(
                time.monotonic(), require_action=False
            ):
                raise RuntimeError(self.gate.reason)
            reason = (
                health_reason(
                    self.health_sample, self.min_headroom, self.max_temperature
                )
                if self.health_sample is not None
                else "Pi health not sampled"
            )
            if reason:
                raise RuntimeError(reason)
            if not self.body_fresh() or not all(
                self.body[n].heartbeat_available
                and not self.body[n].axis_error_flags
                and self.body[n].axis_state in (1, 8)
                for n in step.names
            ):
                raise RuntimeError(
                    "Position move requires fresh idle or closed-loop axes"
                )
            if step.kind == "position_armed":
                if not all(
                    self.body[n].ready and self.body[n].axis_state == 8
                    for n in step.names
                ):
                    raise RuntimeError(
                        "Zero position requires selected axes in closed loop"
                    )
                publisher = self.output
            else:
                publisher = self.moves
            if not publisher.get_subscription_count():
                return None
            self.script_position_at = time.monotonic()
            publisher.publish(
                ActuatorPositionCommand(
                    actuator_names=list(step.names),
                    positions_degrees=list(step.positions),
                )
            )
            future = Future()
            future.set_result(SimpleNamespace(success=True))
            return future
        if step.kind == "motor":
            if step.operation not in ("idle", "emergency", "clear_errors"):
                if self.script_link_required and not self.gate.check(
                    time.monotonic(), require_action=False
                ):
                    raise RuntimeError(self.gate.reason)
                if self.health_sample is None or health_reason(
                    self.health_sample, self.min_headroom, self.max_temperature
                ):
                    raise RuntimeError("Pi health prevents motor operation")
            if not self.motor.service_is_ready():
                return None
            if (
                step.operation == "state"
                and step.state == 8
                and self.script_name in ("home_robot", "calibrate", "full_calibrate")
                and (
                    not self.body_fresh()
                    or any(a.axis_state == 11 for a in self.body.values())
                )
            ):
                raise RuntimeError(
                    "Cannot arm while an actuator is homing or feedback is stale"
                )
            if step.operation == "state" and step.state in (3, 11):
                self.state_cycle = StateCycle(step.names or self.names, step.state)
            return self.motor.call_async(
                MotorCommand.Request(
                    actuator_names=list(step.names),
                    operation=step.operation,
                    state=step.state,
                )
            )
        if step.kind in ("job_start", "job_stop", "job_restart"):
            if not self.jobs.service_is_ready():
                return None
            return self.jobs.call_async(
                SupervisorJob.Request(
                    name=step.operation,
                    start=step.kind == "job_start",
                    operation=step.kind.removeprefix("job_"),
                )
            )
        raise ValueError(f"Unknown script step: {step.kind}")

    def satisfied(self, step):
        if step.kind == "wait_position":
            return (
                self.positions_at > self.script_position_at
                and time.monotonic() - self.positions_at <= self.body_timeout
                and at_position(self.positions, step.names, step.positions)
            )
        if step.kind in ("wait_preflight", "wait_policy_ready"):
            fresh = (
                self.gate.heartbeat_at is not None
                and time.monotonic() - self.gate.heartbeat_at
                <= self.gate.limits.heartbeat_age
            )
            return (
                fresh
                and self.orin_preflight_passed
                and (
                    step.kind == "wait_preflight"
                    or self.orin_policy_ready
                    and self.orin_policy_verified
                    and len(self.orin_bundle_id) == 64
                )
            )

        if step.kind == "wait_policy_stopped":
            return (
                self.gate.heartbeat_at is not None
                and time.monotonic() - self.gate.heartbeat_at
                <= self.gate.limits.heartbeat_age
                and not self.orin_policy_active
            )
        if step.kind == "wait_health":
            return self.health_sample is not None and not health_reason(
                self.health_sample, self.min_headroom, self.max_temperature
            )
        if step.kind == "wait_link":
            healthy = self.gate.check(time.monotonic(), require_action=False)
            self.script_link_required = healthy
            return healthy
        if not self.body_fresh():
            return False
        values = [self.body[n] for n in step.names or self.names]
        if step.kind == "wait_fault_stop":
            return all(
                a.heartbeat_available
                and (a.axis_state == 1 or a.axis_state == 8 and a.ready)
                for a in values
            )
        if step.kind == "wait_cycle":
            return (
                self.state_cycle is not None
                and self.state_cycle.names == step.names
                and self.state_cycle.state == step.state
                and self.state_cycle.complete(self.body)
            )
        if step.kind == "wait_state":
            return all(
                a.heartbeat_available and a.axis_state == step.state for a in values
            )
        if step.kind == "wait_clear":
            return all(a.heartbeat_available and not a.axis_error_flags for a in values)
        if step.kind == "wait_ready":
            return all(
                a.ready
                and a.axis_state == 8
                and a.heartbeat_available
                and not a.axis_error_flags
                for a in values
            )
        raise ValueError(f"Unknown wait step: {step.kind}")

    def clock_probe(self, message):
        received = self.get_clock().now().to_msg()
        self.clock_replies.publish(
            ClockReply(
                id=message.id,
                origin_stamp=message.stamp,
                received_stamp=received,
                reply_stamp=self.get_clock().now().to_msg(),
            )
        )

    def probe(self):
        self.probes.publish(UInt64(data=self.gate.probe(time.monotonic())))

    def heartbeat(self, message):
        if (
            self.script_link_required
            and self.gate.session
            and message.session != self.gate.session
        ):
            self.enter_emergency("Orin session changed during script")
        self.orin_action_sequence = status_sequence(message.action_sequence)
        self.orin_policy_active = message.policy_active
        now = time.monotonic()
        self.gate.heartbeat(
            message.session,
            message.sequence,
            message.degraded,
            message.probe_id,
            now,
            reason=message.reason,
        )
        if self.gate.heartbeat_at == now and self.gate.session == message.session:
            self.orin_preflight_passed = message.preflight_passed
            self.orin_policy_ready = message.policy_ready
            self.orin_policy_verified = message.policy_verified
            self.orin_bundle_id = message.bundle_id
        if self.gate.mode == Mode.DEGRADED:
            self.enter_emergency(self.gate.reason)

    def action(self, message):
        forwarded = self.forward_action(message)
        self.acks.publish(
            PolicyActionAck(
                session=message.session,
                sequence=message.sequence,
                forwarded=bool(forwarded),
            )
        )

    def forward_action(self, message):
        now = time.monotonic()
        command = message.command
        if set(command.actuator_names) != set(self.names):
            if self.gate.mode in (Mode.READY, Mode.RUNNING):
                self.enter_emergency("Policy actuator roster mismatch")
            return
        accepted = self.gate.action(
            message.session,
            message.sequence,
            message.stamp.sec + message.stamp.nanosec * 1e-9,
            self.get_clock().now().nanoseconds * 1e-9,
            now,
            list(command.actuator_names),
            list(command.positions_degrees),
        )
        if self.gate.mode == Mode.DEGRADED:
            self.enter_emergency(self.gate.reason)
        elif accepted:
            # Check local health/body again at the final publication boundary.
            reason = self.local_reason()
            if reason:
                self.enter_local_emergency(reason)
            else:
                self.output.publish(command)
                return True
        return False

    def system_reason(self):
        if self.health_sample is None:
            return "Pi health not sampled"
        reason = health_reason(
            self.health_sample, self.min_headroom, self.max_temperature
        )
        if reason:
            return reason
        if not self.body_fresh():
            return "Foundation state stream stale"
        return ""

    def local_reason(self):
        reason = self.system_reason()
        if reason:
            return reason
        reason = fault_reason(self.body, self.names)
        if reason:
            return reason
        return readiness_reason(self.body)

    def enter_local_emergency(self, reason):
        self.enter_emergency(reason, hold_healthy=not self.system_reason())

    def emergency_steps(self):
        if self.hold_healthy:
            return [Step("motor", "fault_stop"), Step("wait_fault_stop")]
        return self.scripts["emergency"](self.names)

    def emergency_stopped(self):
        return self.satisfied(
            Step("wait_fault_stop")
            if self.hold_healthy
            else Step("wait_state", state=1)
        )

    def sample_health(self):
        now = time.monotonic()
        self.health_sample = self.health.sample(now)
        warning = compute_warning(self.health_sample, self.min_headroom)
        if warning and (
            not getattr(self, "last_compute_warning", "")
            or now - getattr(self, "compute_warning_at", float("-inf")) >= 30.0
        ):
            self.get_logger().warning(warning)
            self.compute_warning_at = now
        self.last_compute_warning = warning

    def enter_emergency(self, reason, *, hold_healthy=False):
        self.recovery_generation += 1
        self.recovery_deadline = None
        # Record degraded verdict before the immediate transition to emergency.
        self.get_logger().error(f"Emergency: {reason}")
        # A subsequent actuator fault cannot weaken an all-axis e-stop.
        self.hold_healthy = hold_healthy and (
            self.gate.mode != Mode.EMERGENCY or self.hold_healthy
        )
        self.gate.emergency(reason)
        self.script_link_required = False
        self.script_name = "emergency"
        self.runner.start(self.emergency_steps())
        self.emergency_attempt = time.monotonic()
        # Remote failure cannot delay local IDLE. Both requests are asynchronous.
        self.stop_policy()

    def stop_policy(self):
        if self.jobs.service_is_ready():
            self.remote_stop_at = time.monotonic()
            self.jobs.call_async(SupervisorJob.Request(name="policy", start=False))

    def missing_controller_axes(self):
        online = (
            {
                axis.axis_id
                for axis in self.body.values()
                if axis.heartbeat_available
                and axis.heartbeat_monotonic_seconds
                > self.reboot_since.get(axis.axis_id, -1)
            }
            if self.body_fresh()
            else set()
        )
        return sorted(set(range(12)) - online)

    async def reboot_controllers(self, request, response):
        names = set(request.actuator_names)
        if bool(names) == request.all_controllers or not names.issubset(self.names):
            response.message = "Select known actuator names or all_controllers"
            return response
        operator_stop = (
            self.gate.mode == Mode.EMERGENCY
            and self.gate.reason == "operator emergency"
        )
        disarmed = (
            self.gate.mode == Mode.IDLE
            and not self.runner.active
            and self.emergency_stopped()
        )
        if (
            not (operator_stop or disarmed)
            or self.reboot_wait
            or self.recovery_deadline is not None
        ):
            response.message = "Requires disarmed or operator emergency with no recovery or reboot in progress"
            return response
        timeout = self.get_parameter("controller_reconnect_timeout").value
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not self.reboot_client.service_is_ready()
        ):
            response.message = "Invalid reconnect timeout or Foundation unavailable"
            return response
        if disarmed:
            self.enter_emergency("operator emergency")
        done = RosFuture()
        try:
            future = self.reboot_client.call_async(request)
            self.reboot_wait = (time.monotonic() + timeout, future, done, response)
            await done
        finally:
            self.reboot_wait = None
        return response

    def update_reboot(self, now):
        if self.reboot_wait is None:
            return
        deadline, future, done, response = self.reboot_wait
        if done.done():
            return
        if future.done():
            if future.exception() is not None:
                response.message = str(future.exception())
                done.set_result(None)
                return
            result = future.result()
            if not response.sent_boards:
                response.sent_boards = list(result.sent_boards)
                for board in response.sent_boards:
                    self.reboot_since.update({board: now, board + 1: now})
            missing = set(self.missing_controller_axes())
            response.reconnected_boards = [
                board
                for board in response.sent_boards
                if not {board, board + 1} & missing
            ]
            if len(response.reconnected_boards) == len(response.sent_boards):
                response.success = result.success
                response.message = result.message + "; heartbeat monitoring complete"
                done.set_result(None)
                return
        if now >= deadline:
            response.message = (
                "Timed out waiting for Foundation or controller heartbeats"
            )
            done.set_result(None)

    def tick(self):
        now = time.monotonic()
        self.update_reboot(now)
        if self.recovery_deadline is not None and now >= self.recovery_deadline:
            self.enter_emergency("Foundation recovery timed out")
        if self.gate.mode == Mode.EMERGENCY and self.hold_healthy:
            reason = self.system_reason()
            if reason:
                self.enter_emergency(reason)
        if (
            self.runner.active
            and (
                self.script_name in ("home_robot", "zero_all")
                or (
                    self.script_name in ("calibrate", "full_calibrate")
                    and self.state_cycle is not None
                )
            )
        ) or self.gate.mode == Mode.HOLDING:
            reason = self.homing_fault()
            if not reason and self.gate.mode == Mode.HOLDING:
                reason = self.local_reason()
            if reason:
                self.enter_local_emergency(reason)
        if self.runner.active and self.local_script():
            reason = (
                health_reason(
                    self.health_sample, self.min_headroom, self.max_temperature
                )
                if self.health_sample is not None
                else "Pi health not sampled"
            )
            if reason or not self.body_fresh():
                self.enter_emergency(reason or "Foundation state stream stale")
        if self.gate.mode == Mode.EMERGENCY and now - self.remote_stop_at >= 1.0:
            self.stop_policy()
        if (
            self.runner.active
            and self.script_link_required
            and self.health_sample is not None
        ):
            reason = health_reason(
                self.health_sample, self.min_headroom, self.max_temperature
            )
            if reason:
                self.enter_emergency(reason)
        if self.gate.mode in (Mode.READY, Mode.RUNNING):
            reason = self.local_reason()
            if reason:
                self.enter_local_emergency(reason)
            elif not self.gate.check(now):
                self.enter_emergency(self.gate.reason)
        elif self.runner.active and self.script_link_required:
            if not self.gate.check(now, require_action=False) or not self.body_fresh():
                self.enter_emergency(
                    "Link or Foundation lost during script: " + self.gate.reason
                )
        elif (
            self.gate.mode == Mode.EMERGENCY
            and not self.runner.active
            and now - self.emergency_attempt >= 1.0
        ) and not self.emergency_stopped():
            self.emergency_attempt = now
            self.script_name = "emergency"
            self.runner.start(self.emergency_steps())
        self.runner.tick(now)
        if self.runner.error:
            if self.gate.mode != Mode.EMERGENCY:
                if not self.system_reason() and fault_reason(self.body, self.names):
                    self.enter_local_emergency(self.runner.error)
                else:
                    self.enter_emergency(self.runner.error)
            elif now - self.emergency_attempt >= 1.0:
                self.emergency_attempt = now
                self.runner.start(self.emergency_steps())
        elif not self.runner.active and self.script_name:
            name, self.script_name = self.script_name, ""
            if name == "boot":
                self.gate.mode = Mode.IDLE
            elif name == "shutdown":
                self.gate.mode = Mode.SHUTDOWN
                self.gate.reason = "shutdown complete"
            elif (
                name not in ("startup", "restart_policy", "emergency")
                and not self.script_link_required
            ):
                reason = self.local_reason()
                if reason:
                    self.enter_local_emergency(reason)
                else:
                    self.gate.mode = Mode.HOLDING
                    self.gate.reason = (
                        f"{name} complete; local hold, policy forwarding disabled"
                    )
            elif name != "emergency":
                reason = self.local_reason()
                if reason:
                    self.enter_local_emergency(reason)
                elif not self.gate.check(now):
                    self.enter_emergency(self.gate.reason)
                else:
                    self.gate.mode = Mode.READY
        prompt = self.runner.prompt
        health = self.health_sample

        health_message = SupervisorHealth(
            available=status_bool(health is not None),
            sample_monotonic_seconds=status_float(
                health.get("sample_monotonic_seconds", 0.0)
                if health is not None
                else 0.0
            ),
            cpu_count=status_uint32(
                health.get("cpu_count", 0) if health is not None else 0
            ),
            interface=status_string(
                health.get("interface", "") if health is not None else ""
            ),
            interface_state=status_string(
                health.get("interface_state", "") if health is not None else ""
            ),
            temperature_available=status_bool(
                health is not None and health.get("temperature_c") is not None
            ),
            temperature_c=status_float(health.get("temperature_c", 0.0))
            if health is not None and health.get("temperature_c") is not None
            else 0.0,
            system_cpu_headroom_available=status_bool(
                health is not None
                and health.get("system_cpu_headroom_percent") is not None
            ),
            system_cpu_headroom_percent=status_float(
                health.get("system_cpu_headroom_percent", 0.0)
            )
            if health is not None
            and health.get("system_cpu_headroom_percent") is not None
            else 0.0,
            foundation_cpu_available=status_bool(
                health is not None
                and health.get("foundation_cpu_percent_one_core") is not None
            ),
            foundation_cpu_percent_one_core=status_float(
                health.get("foundation_cpu_percent_one_core", 0.0)
            )
            if health is not None
            and health.get("foundation_cpu_percent_one_core") is not None
            else 0.0,
            policy_only_baseline_percent_one_core=status_float(
                health.get("policy_only_baseline_percent_one_core", 0.0)
            )
            if health is not None
            else 0.0,
            baseline_source=status_string(
                health.get("baseline_source", "") if health is not None else ""
            ),
            foundation_pid=status_uint32(
                health.get("foundation_pid", 0) if health is not None else 0
            ),
            errors=[
                status_string(error)
                for error in (health.get("errors", []) if health is not None else [])
            ],
        )
        self.status.publish(
            SupervisorStatus(
                stamp=self.get_clock().now().to_msg(),
                mode=status_string(self.gate.mode.value),
                reason=status_string(self.gate.reason),
                stop_behavior=status_string(
                    "hold_healthy" if self.hold_healthy else "idle_all"
                ),
                script=status_string(self.script_name),
                script_step=status_uint32(self.runner.index),
                script_error=status_string(self.runner.error),
                operator_prompt=SupervisorOperatorPrompt(
                    id=status_string("" if prompt is None else prompt.get("id", "")),
                    text=status_string(
                        "" if prompt is None else prompt.get("text", "")
                    ),
                ),
                available_scripts=[
                    status_string(name)
                    for name in sorted(
                        name for name in self.scripts if name != "emergency"
                    )
                ],
                session=status_string(self.gate.session),
                action_sequence=status_sequence(self.gate.action_sequence),
                heartbeat_sequence=status_sequence(self.gate.heartbeat_sequence),
                orin_action_sequence=status_sequence(self.orin_action_sequence),
                orin_policy_active=status_bool(self.orin_policy_active),
                orin_preflight_passed=status_bool(self.orin_preflight_passed),
                orin_policy_ready=status_bool(self.orin_policy_ready),
                orin_policy_verified=status_bool(self.orin_policy_verified),
                orin_bundle_id=status_string(self.orin_bundle_id),
                rtt_available=status_bool(self.gate.rtt is not None),
                rtt_ms=status_float(
                    0.0 if self.gate.rtt is None else self.gate.rtt * 1000
                ),
                jitter_ms=status_float(self.gate.jitter * 1000),
                missing_controller_heartbeat_axes=self.missing_controller_axes(),
                health=health_message,
            )
        )

    def respond(self, request, response):
        try:
            self.runner.respond(request.name, time.monotonic())
            response.success, response.message = True, "operator confirmation accepted"
        except ValueError as error:
            response.success, response.message = False, str(error)
        return response

    def run_script(self, request, response):
        try:
            if request.name not in self.scripts or request.name == "emergency":
                raise ValueError("Unknown script; emergency uses its dedicated service")
            if request.name == "startup" and self.gate.mode != Mode.IDLE:
                raise ValueError("Startup requires idle mode")
            steps = self.scripts[request.name](self.names)
            if request.name == "home_robot":
                reason = self.homing_fault()
                if reason:
                    raise ValueError(reason)
            if request.name == "zero_all":
                reason = self.homing_fault()
                if reason:
                    raise ValueError(reason)
            if request.name in {f"zero_{axis}" for axis in self.names}:
                reason = self.local_reason()
                if reason:
                    raise ValueError(reason)
                if not all(self.body[name].axis_state == 8 for name in self.names):
                    raise ValueError("Zero position requires all axes in closed loop")
            if request.name == "shutdown":
                # Shutdown preempts every script and closes the gate immediately.
                self.gate.mode = Mode.SHUTDOWN
                self.gate.reason = "shutdown requested"
            else:
                if self.runner.active or self.gate.mode not in (
                    Mode.IDLE,
                    Mode.READY,
                    Mode.HOLDING,
                ):
                    raise ValueError(
                        "Scripts require idle, ready or holding mode and no active script"
                    )
                self.gate.mode = Mode.BOOT
            self.state_cycle = None
            self.runner.start(steps)
            # Scripts opt into the Orin watchdog explicitly with wait_link.
            self.script_link_required = False
            self.script_name = request.name
            response.success, response.message = (
                True,
                "accepted; inspect /rpi/supervisor/status for completion",
            )
        except (ValueError, KeyError) as error:
            response.success, response.message = False, str(error)
        return response

    def run(self, request, response):
        try:
            reason = self.local_reason()
            if reason:
                raise ValueError(reason)
            self.gate.start(time.monotonic())
            response.success, response.message = True, "running"
        except ValueError as error:
            response.success, response.message = False, str(error)
        return response

    def policy_stop(self, request, response):
        # Close forwarding before the asynchronous stop request. Keep local hold.
        if self.gate.mode in (Mode.READY, Mode.RUNNING):
            self.gate.mode = Mode.HOLDING
            self.gate.reason = "policy stop requested; holding locally"
        if not self.jobs.service_is_ready():
            response.success, response.message = (
                False,
                "Orin job service unavailable; forwarding closed",
            )
        else:
            self.stop_policy()
            response.success, response.message = (
                True,
                "policy stop requested; inspect Orin status",
            )
        return response

    def idle(self, request, response):
        if self.gate.mode != Mode.RUNNING:
            response.success, response.message = (
                False,
                "Idle requires running; emergency or shutdown disarms",
            )
        else:
            self.gate.mode = Mode.READY
            response.success, response.message = True, "ready; holding last target"
        return response

    def emergency(self, request, response):
        self.enter_emergency("operator emergency")
        response.success, response.message = True, "emergency latched"
        return response

    def recover(self, request, response):
        if (
            self.gate.mode != Mode.EMERGENCY
            or self.runner.active
            or self.reboot_wait is not None
            or not self.emergency_stopped()
            or (self.hold_healthy and bool(fault_reason(self.body, self.names)))
        ):
            response.success, response.message = (
                False,
                "Recovery requires confirmed stopped axes and cleared actuator faults",
            )
        else:
            if not self.motor.service_is_ready():
                response.success, response.message = (
                    False,
                    "Foundation motor service unavailable",
                )
                return response
            self.recovery_generation += 1
            generation = self.recovery_generation
            self.recovery_deadline = time.monotonic() + 3.0
            future = self.motor.call_async(MotorCommand.Request(operation="recover"))

            def complete(result_future):
                if generation != self.recovery_generation:
                    return
                self.recovery_deadline = None
                try:
                    result = result_future.result()
                    if result is None or not result.success:
                        raise RuntimeError(
                            getattr(result, "message", "Foundation recovery failed")
                        )
                    if (
                        self.gate.mode != Mode.EMERGENCY
                        or self.runner.active
                        or self.reboot_wait is not None
                        or not self.emergency_stopped()
                        or (
                            self.hold_healthy
                            and bool(fault_reason(self.body, self.names))
                        )
                    ):
                        raise RuntimeError("Recovery lost confirmed stopped axes")
                    self.gate.recover()
                    self.hold_healthy = False
                except (OSError, RuntimeError, ValueError) as error:
                    self.enter_emergency(str(error), hold_healthy=self.hold_healthy)

            future.add_done_callback(complete)
            response.success, response.message = (
                True,
                "recovery requested; wait for idle status",
            )
        return response


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    handlers = {
        sig: signal.signal(sig, signal.default_int_handler)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    node = None
    try:
        node = RpiSupervisor()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if node is not None:
                try:
                    # No ROS calls if another owner already shut down the context.
                    if rclpy.ok():
                        node.enter_emergency("RPi Supervisor exiting")
                        deadline = time.monotonic() + 3.0
                        while (
                            rclpy.ok()
                            and node.runner.active
                            and time.monotonic() < deadline
                        ):
                            rclpy.spin_once(node, timeout_sec=0.02)
                except ExternalShutdownException:
                    pass
                finally:
                    node.destroy_node()
        finally:
            try:
                rclpy.try_shutdown()
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
