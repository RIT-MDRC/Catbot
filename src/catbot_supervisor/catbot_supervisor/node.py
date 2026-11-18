"""RPi Supervisor: sole policy-to-Foundation gateway and robot sequencer."""

import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String, UInt64
from std_srvs.srv import Trigger

from catbot_interfaces.msg import (
    ActuatorPositionCommand,
    BodyErrorState,
    OrinHeartbeat,
    PolicyAction,
    PolicyActionAck,
)
from catbot_interfaces.srv import MotorCommand, RunScript, SupervisorJob
from catbot_supervisor.core import ActionGate, Limits, Mode
from catbot_supervisor.health import PiHealth, health_reason
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
        self.scripts = registry()
        self.script_name = ""
        self.script_link_required = False
        self.orin_action_sequence = 0
        self.orin_policy_active = False
        self.emergency_attempt = float("-inf")
        self.motor = self.create_client(MotorCommand, "/body/control/motor")
        self.jobs = self.create_client(SupervisorJob, "/orin/supervisor/job")
        self.output = self.create_publisher(
            ActuatorPositionCommand, "/body/control/position", 1
        )
        self.acks = self.create_publisher(
            PolicyActionAck, "/rpi/supervisor/action_ack", 1
        )
        self.probes = self.create_publisher(UInt64, "/orin/supervisor/probe", 1)
        self.status = self.create_publisher(
            String,
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
        for name, callback in (
            ("run", self.run),
            ("idle", self.idle),
            ("emergency", self.emergency),
            ("recover", self.recover),
        ):
            self.create_service(Trigger, "/rpi/supervisor/" + name, callback)
        self.create_timer(0.02, self.tick)
        self.create_timer(0.1, self.probe)
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

    def body_fresh(self):
        return bool(self.body) and time.monotonic() - self.body_at <= self.body_timeout

    def dispatch(self, step):
        if step.kind == "motor":
            if step.operation not in ("idle", "clear_errors"):
                if not self.gate.check(time.monotonic(), require_action=False):
                    raise RuntimeError(self.gate.reason)
                if self.health_sample is None or health_reason(
                    self.health_sample, self.min_headroom, self.max_temperature
                ):
                    raise RuntimeError("Pi health prevents motor operation")
            if not self.motor.service_is_ready():
                return None
            return self.motor.call_async(
                MotorCommand.Request(
                    actuator_names=list(step.names),
                    operation=step.operation,
                    state=step.state,
                )
            )
        if step.kind in ("job_start", "job_stop"):
            if not self.jobs.service_is_ready():
                return None
            return self.jobs.call_async(
                SupervisorJob.Request(
                    name=step.operation, start=step.kind == "job_start"
                )
            )
        raise ValueError(f"Unknown script step: {step.kind}")

    def satisfied(self, step):
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
        if step.kind == "wait_state":
            return all(
                a.heartbeat_available and a.axis_state == step.state for a in values
            )
        if step.kind == "wait_clear":
            return all(a.heartbeat_available and not a.axis_error_flags for a in values)
        if step.kind == "wait_ready":
            return all(
                a.ready and a.heartbeat_available and not a.axis_error_flags
                for a in values
            )
        raise ValueError(f"Unknown wait step: {step.kind}")

    def probe(self):
        self.probes.publish(UInt64(data=self.gate.probe(time.monotonic())))

    def heartbeat(self, message):
        if (
            self.script_link_required
            and self.gate.session
            and message.session != self.gate.session
        ):
            self.enter_emergency("Orin session changed during script")
        self.orin_action_sequence = message.action_sequence
        self.orin_policy_active = message.policy_active
        self.gate.heartbeat(
            message.session,
            message.sequence,
            message.degraded,
            message.probe_id,
            time.monotonic(),
        )
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
                self.enter_emergency(reason)
            else:
                self.output.publish(command)
                return True
        return False

    def local_reason(self):
        if self.health_sample is None:
            return "Pi health not sampled"
        reason = health_reason(
            self.health_sample, self.min_headroom, self.max_temperature
        )
        if reason:
            return reason
        if not self.body_fresh():
            return "Foundation state stream stale"
        if not all(
            a.ready and a.heartbeat_available and not a.axis_error_flags
            for a in self.body.values()
        ):
            return "Foundation actuator unavailable or not ready"
        return ""

    def sample_health(self):
        self.health_sample = self.health.sample(time.monotonic())

    def enter_emergency(self, reason):
        if self.gate.mode == Mode.EMERGENCY:
            return
        # Record degraded verdict before the immediate transition to emergency.
        self.get_logger().error(f"Emergency: {reason}")
        self.gate.emergency(reason)
        self.script_link_required = False
        self.script_name = "emergency"
        self.runner.start(self.scripts["emergency"](self.names))
        self.emergency_attempt = time.monotonic()
        # Remote failure cannot delay local IDLE. Both requests are asynchronous.
        if self.jobs.service_is_ready():
            self.jobs.call_async(SupervisorJob.Request(name="policy", start=False))

    def tick(self):
        now = time.monotonic()
        if self.gate.mode in (Mode.READY, Mode.RUNNING):
            reason = self.local_reason()
            if reason or not self.gate.check(now):
                self.enter_emergency(reason or self.gate.reason)
        elif self.runner.active and self.script_link_required:
            if not self.gate.check(now, require_action=False) or not self.body_fresh():
                self.enter_emergency(
                    "Link or Foundation lost during script: " + self.gate.reason
                )
        elif (
            self.gate.mode == Mode.EMERGENCY
            and not self.runner.active
            and now - self.emergency_attempt >= 1.0
        ) and not self.satisfied(Step("wait_state", state=1)):
            self.emergency_attempt = now
            self.script_name = "emergency"
            self.runner.start(self.scripts["emergency"](self.names))
        self.runner.tick(now)
        if self.runner.error:
            if self.gate.mode != Mode.EMERGENCY:
                self.enter_emergency(self.runner.error)
            elif now - self.emergency_attempt >= 1.0:
                self.emergency_attempt = now
                self.runner.start(self.scripts["emergency"](self.names))
        elif not self.runner.active and self.script_name:
            name, self.script_name = self.script_name, ""
            if name == "boot":
                self.gate.mode = Mode.IDLE
            elif name == "shutdown":
                self.gate.mode = Mode.SHUTDOWN
                self.gate.reason = "shutdown complete"
            elif name != "emergency":
                reason = self.local_reason()
                if reason or not self.gate.check(now):
                    self.enter_emergency(reason or self.gate.reason)
                else:
                    self.gate.mode = Mode.READY
        self.status.publish(
            String(
                data=json.dumps(
                    {
                        "mode": self.gate.mode.value,
                        "reason": self.gate.reason,
                        "script": self.script_name,
                        "script_step": self.runner.index,
                        "script_error": self.runner.error,
                        "session": self.gate.session,
                        "action_sequence": self.gate.action_sequence,
                        "heartbeat_sequence": self.gate.heartbeat_sequence,
                        "orin_action_sequence": self.orin_action_sequence,
                        "orin_policy_active": self.orin_policy_active,
                        "rtt_ms": None
                        if self.gate.rtt is None
                        else self.gate.rtt * 1000,
                        "jitter_ms": self.gate.jitter * 1000,
                        "health": self.health_sample,
                    },
                    allow_nan=False,
                )
            )
        )

    def run_script(self, request, response):
        try:
            if request.name not in self.scripts or request.name == "emergency":
                raise ValueError("Unknown script; emergency uses its dedicated service")
            if request.name == "startup" and self.gate.mode != Mode.IDLE:
                raise ValueError("Startup requires idle mode")
            if request.name == "shutdown":
                # Shutdown preempts every script and closes the gate immediately.
                self.gate.mode = Mode.SHUTDOWN
                self.gate.reason = "shutdown requested"
            else:
                if self.runner.active or self.gate.mode not in (Mode.IDLE, Mode.READY):
                    raise ValueError(
                        "Scripts require idle or ready mode and no active script"
                    )
                self.gate.mode = Mode.BOOT
            self.runner.start(self.scripts[request.name](self.names))
            self.script_link_required = request.name not in ("startup", "shutdown")
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
            or not self.satisfied(Step("wait_state", state=1))
        ):
            response.success, response.message = (
                False,
                "Recovery requires confirmed idle axes after emergency script",
            )
        else:
            self.gate.recover()
            response.success, response.message = True, "idle; run startup explicitly"
        return response


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = RpiSupervisor()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            # Keep ROS alive briefly to dispatch and confirm local IDLE on normal exit.
            node.enter_emergency("RPi Supervisor exiting")
            deadline = time.monotonic() + 3.0
            while rclpy.ok() and node.runner.active and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.02)
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
