"""Orin policy lifecycle, resource telemetry and preflight; Pi owns robot modes."""

import json
import math
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import rclpy
from catbot_policy.configuration import POLICY_DEFAULTS
from catbot_policy.recording import SessionRecorder
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import UInt64

from catbot_interfaces.msg import (
    ClockProbe,
    ClockReply,
    OrinHeartbeat,
    OrinTelemetry,
    PolicyAction,
    PolicyReady,
    SupervisorStatus,
)
from catbot_interfaces.srv import GetSupervisorStatus, SupervisorJob
from catbot_supervisor.configuration import ORIN_DEFAULTS
from catbot_supervisor.jobs import Jobs
from catbot_supervisor.offline import OfflineQueue
from catbot_supervisor.preflight import (
    ClockMonitor,
    ComputeProbe,
    compute_warning,
    pi_link_status,
    policy_fault,
    seconds,
    verdict,
)
from catbot_supervisor.telemetry import Resources


class OrinSupervisor(Node):
    def __init__(self):
        super().__init__("orin_supervisor")

        def param(name, default):
            return self.declare_parameter(name, ORIN_DEFAULTS.get(name, default)).value

        self.policy_parameters = {
            name: param(name, value)
            for name, value in POLICY_DEFAULTS.items()
            if name != "simulation_mode"
        }
        self.simulation_mode = bool(param("simulation_mode", False))
        self.timeout = float(param("action_timeout", 0.25))
        self.lease_timeout = float(param("pi_lease_timeout", 0.5))
        self.max_temperature = float(param("max_temperature_c", 80.0))
        self.min_disk = int(param("min_disk_free_bytes", 1073741824))
        if (
            not all(
                math.isfinite(v) and v > 0
                for v in (self.timeout, self.lease_timeout, self.max_temperature)
            )
            or self.min_disk < 0
        ):
            raise ValueError("Invalid Orin preflight limits")
        self.clock = ClockMonitor(float(param("clock_tolerance", 0.05)))
        self.clock_sequence = time.monotonic_ns()
        self.resources = Resources(
            str(param("disk_path", "/")),
            Path(str(param("resource_proc_root", "/proc"))),
            Path(str(param("resource_sys_root", "/sys"))),
        )
        self.resource_sample = None
        self.compute = ComputeProbe(
            self.policy_parameters, float(param("compute_probe_timeout", 30.0))
        )
        self.tags = {
            "run_id": str(param("supervisor_run_id", ""))
            or str(self.policy_parameters["run_id"])
            or uuid.uuid4().hex,
            "scenario": str(param("scenario", "unspecified")),
            "git_commit": str(param("git_commit", "")),
        }
        if not self.tags["git_commit"]:
            try:
                self.tags["git_commit"] = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                ).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                self.tags["git_commit"] = "unknown"
        commands = json.loads(str(param("jobs_json", "{}")))
        if not isinstance(commands, dict) or "policy" in commands:
            raise ValueError("jobs_json must be an object; policy is reserved")
        offline_commands = json.loads(str(param("offline_jobs_json", "{}")))
        if (
            not isinstance(offline_commands, dict)
            or set(offline_commands) & set(commands)
            or "policy" in offline_commands
        ):
            raise ValueError("offline job names must be distinct from managed jobs")
        # Validate raw argv before wrapping it in the resource envelope.
        Jobs(offline_commands)
        self.offline = OfflineQueue(
            {
                name: [
                    sys.executable,
                    "-m",
                    "catbot_supervisor.offline_worker",
                    "--",
                    *argv,
                ]
                for name, argv in offline_commands.items()
            }
        )
        self.pi_idle_at = None
        self.create_subscription(
            SupervisorStatus, "/rpi/supervisor/status", self.pi_status, 1
        )
        self.recording_root = str(
            param("recording_directory", "~/.local/share/catbot/recordings")
        )
        self.recording_topics = list(
            param(
                "recording_topics",
                [
                    "/policy/feedback",
                    "/policy/recording/status",
                    "/orin/policy/action",
                    "/rpi/supervisor/action_ack",
                    "/tf",
                    "/tf_static",
                    "/diagnostics",
                    "/body/state/error",
                    "/zed/zed_node/imu/data",
                    "/zed/zed_node/odom",
                    "/body/state/position",
                    "/parameter_events",
                    "/orin/supervisor/telemetry",
                    "/rpi/supervisor/status",
                ],
            )
        )
        self.recording = None
        if "recording" in commands or "recording" in offline_commands:
            raise ValueError("recording is a reserved managed job")
        commands["recording"] = ["ros2", "bag", "record", "-s", "mcap"]
        self.operator = str(param("operator", ""))
        self.session = uuid.uuid4().hex
        self.policy_ready = self.policy_verified = False
        self.bundle_id = self.load_error = ""
        self.probe_id = self.sequence = self.action_sequence = 0
        self.action_at = self.probe_at = None
        self.jobs = Jobs(
            {**commands, "policy": self.policy_command()},
            before_start=self.before_start,
        )
        self.publisher = self.create_publisher(
            OrinHeartbeat, "/orin/supervisor/heartbeat", 1
        )
        self.telemetry = self.create_publisher(
            OrinTelemetry, "/orin/supervisor/telemetry", 1
        )
        self.clock_publisher = self.create_publisher(
            ClockProbe, "/orin/supervisor/clock_probe", 1
        )
        self.create_subscription(
            ClockReply, "/rpi/supervisor/clock_reply", self.clock_reply, 1
        )
        self.create_subscription(UInt64, "/orin/supervisor/probe", self.probe, 1)
        self.create_subscription(PolicyAction, "/orin/policy/action", self.action, 1)
        self.create_subscription(
            PolicyReady,
            "/orin/policy/ready",
            self.readiness,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.create_service(SupervisorJob, "/orin/supervisor/job", self.job)
        self.create_service(
            GetSupervisorStatus, "/orin/supervisor/get_status", self.get_status
        )
        self.create_timer(0.05, self.tick)
        self.create_timer(0.25, self.clock_probe)
        self.create_timer(1.0, self.sample_resources)
        self.sample_resources()
        self.compute.start(time.monotonic())

    def policy_command(self):
        command = ["ros2", "run", "catbot_policy", "policy", "--ros-args"]
        parameters = {
            **self.policy_parameters,
            "action_session": self.session,
            "recording_directory": self.recording_root,
            "simulation_mode": self.simulation_mode,
            "supervised_actions": True,
            "require_provider_contract": True,
            "provider_contract_topic": "/policy/contract",
        }
        for name, value in parameters.items():
            command += ["-p", f"{name}:={json.dumps(value)}"]
        return command

    def pi_status_snapshot(self):
        return pi_link_status(self.probe_at, time.monotonic(), self.lease_timeout)

    def preflight_reason(self):
        pi = self.pi_status_snapshot()
        if not pi["available"]:
            return pi["reason"]
        return verdict(
            self.resource_sample,
            self.clock,
            self.compute,
            time.monotonic(),
            self.max_temperature,
            self.min_disk,
        )

    def before_start(self, name):
        now = time.monotonic()
        if name == "policy":
            self.offline.tick(now, idle=False)
            if self.offline.jobs.children:
                raise ValueError("Offline processes are stopping; retry after cleanup")
        if self.probe_at is None or now - self.probe_at > self.lease_timeout:
            raise ValueError(self.pi_status_snapshot()["reason"])
        reason = self.preflight_reason()
        if reason:
            raise ValueError("Preflight failed: " + reason)
        if name == "recording":
            if self.recording is not None:
                self.recording.close()
            self.recording = SessionRecorder(
                self.recording_root,
                {
                    **self.tags,
                    "operator": self.operator,
                    "policy_bundle_id": self.bundle_id,
                    "configuration": self.policy_parameters,
                    "clock": self.clock.status(now),
                },
            )
            self.jobs.commands[name] = self.recording.mcap_command(
                self.recording_topics
            )
        if name == "policy":
            self.session = uuid.uuid4().hex
            self.sequence = self.action_sequence = 0
            self.action_at = None
            self.policy_ready = self.policy_verified = False
            self.bundle_id, self.load_error = "", "loading"
            self.jobs.commands["policy"] = self.policy_command()

    def clock_probe(self):
        self.clock_sequence += 1
        stamp = self.get_clock().now().to_msg()
        self.clock.sent(self.clock_sequence, seconds(stamp), time.monotonic())
        self.clock_publisher.publish(ClockProbe(id=self.clock_sequence, stamp=stamp))

    def clock_reply(self, message):
        self.clock.reply(
            message.id,
            seconds(message.origin_stamp),
            seconds(message.received_stamp),
            seconds(message.reply_stamp),
            self.get_clock().now().nanoseconds * 1e-9,
            time.monotonic(),
        )

    def pi_status(self, message):
        self.pi_idle_at = (
            time.monotonic()
            if message.mode == "idle" and not message.script
            else None
        )

    def probe(self, message):
        self.probe_id, self.probe_at = message.data, time.monotonic()

    def readiness(self, message):
        if message.session != self.session or not self.jobs.running("policy"):
            return
        valid_hash = len(message.bundle_id) == 64 and all(
            c in "0123456789abcdef" for c in message.bundle_id
        )
        self.policy_verified = bool(message.verified and valid_hash)
        self.policy_ready = bool(message.ready and self.policy_verified)
        self.bundle_id = message.bundle_id if self.policy_verified else ""
        self.load_error = (
            "" if self.policy_ready else message.detail or "policy bundle not verified"
        )

    def action(self, message):
        if message.session == self.session and message.sequence > self.action_sequence:
            self.action_sequence, self.action_at = message.sequence, time.monotonic()

    def job(self, request, response):
        try:
            operation = request.operation or ("start" if request.start else "stop")
            if operation not in ("start", "stop", "restart"):
                raise ValueError("Operation must be start, stop, or restart")
            if request.name in self.offline.jobs.commands:
                if operation == "stop":
                    self.offline.cancel(request.name, time.monotonic())
                else:
                    if self.jobs.children.get("policy") is not None:
                        raise ValueError("Offline work requires policy stopped")
                    self.offline.enqueue(request.name)
                response.success, response.message = True, "offline request accepted"
                return response
            self.jobs.validate_name(request.name)
            if operation != "stop":
                reason = self.preflight_reason()
                if reason:
                    raise ValueError("Preflight failed: " + reason)
                if (
                    self.probe_at is None
                    or time.monotonic() - self.probe_at > self.lease_timeout
                ):
                    raise ValueError(self.pi_status_snapshot()["reason"])
            getattr(self.jobs, operation)(request.name, time.monotonic())
            if request.name == "policy" and operation == "stop":
                self.policy_ready = self.policy_verified = False
                self.load_error = self.bundle_id = ""
                self.jobs.errors.pop("policy", None)
            response.success, response.message = (
                True,
                "accepted; query get_status for completion",
            )
        except (ValueError, OSError) as error:
            response.success, response.message = False, str(error)
        return response

    def get_status(self, request, response):
        try:
            value = {
                "version": 1,
                "jobs": self.jobs.status(request.name)
                if request.name not in self.offline.jobs.commands
                else {},
                "offline": self.offline.status(),
                "pi": self.pi_status_snapshot(),
                "policy": {
                    "state": self.jobs.status("policy")["policy"]["state"],
                    "session": self.session,
                    "ready": self.policy_ready and self.jobs.running("policy"),
                    "verified": self.policy_verified,
                    "bundle_id": self.bundle_id,
                    "load_error": self.load_error,
                },
                "preflight": {
                    "passed": not self.preflight_reason(),
                    "reason": self.preflight_reason(),
                },
                "clock": self.clock.status(time.monotonic()),
                "tags": self.tags,
                "resources": self.resource_sample,
            }
            response.status_json = json.dumps(value, allow_nan=False)
            response.success, response.message = True, "status"
        except ValueError as error:
            response.success, response.message = False, str(error)
        return response

    def sample_resources(self):
        self.resource_sample = self.resources.sample()
        sample = self.resource_sample
        self.telemetry.publish(
            OrinTelemetry(
                stamp=self.get_clock().now().to_msg(),
                cpu_percent=sample["cpu_percent"]
                if sample["cpu_percent"] is not None
                else math.nan,
                gpu_percent=sample["gpu_percent"]
                if sample["gpu_percent"] is not None
                else math.nan,
                temperature_c=sample["temperature_c"]
                if sample["temperature_c"] is not None
                else math.nan,
                memory_used_bytes=sample["memory_used_bytes"],
                memory_total_bytes=sample["memory_total_bytes"],
                disk_free_bytes=sample["disk_free_bytes"],
                disk_total_bytes=sample["disk_total_bytes"],
                resources_valid=not bool(sample["errors"]),
                gpu_available=sample["gpu_percent"] is not None,
                bundle_id=self.bundle_id,
                detail="; ".join(sample["errors"]),
                **self.tags,
            )
        )

    def tick(self):
        now = time.monotonic()
        clock_status = self.clock.status(now)
        if clock_status["warning"] and now - getattr(self, "clock_warning_at", float("-inf")) >= 30.0:
            self.get_logger().warning(
                "Pi clock offset %.3f ms, uncertainty %.3f ms, bound %.3f ms"
                % (clock_status["offset_seconds"] * 1000, clock_status["uncertainty_seconds"] * 1000, clock_status["bound_seconds"] * 1000)
            )
            self.clock_warning_at = now
        self.compute.tick(now)
        warning = compute_warning(self.resource_sample, self.compute)
        if warning and (
            not getattr(self, "last_compute_warning", "")
            or now - getattr(self, "compute_warning_at", float("-inf")) >= 30.0
        ):
            self.get_logger().warning("Compute advisory: " + warning)
            self.compute_warning_at = now
        self.last_compute_warning = warning
        lease_lost = self.probe_at is None or now - self.probe_at > self.lease_timeout
        if lease_lost:
            for name in self.jobs.commands:
                self.jobs.stop(name, now)
        if self.recording is not None:
            if shutil.disk_usage(self.recording.path).free < self.min_disk:
                self.jobs.stop("recording", now)
            if "recording" not in self.jobs.children:
                self.recording.close()
                self.recording = None
        self.jobs.tick(now)
        self.offline.tick(
            now,
            idle=not lease_lost
            and self.pi_idle_at is not None
            and 0 <= now - self.pi_idle_at <= self.lease_timeout
            and "policy" not in self.jobs.children
            and "policy" not in self.jobs.pending,
        )
        preflight = self.preflight_reason()
        reason = self.pi_status_snapshot()["reason"] if lease_lost else preflight
        if not reason:
            reason = policy_fault(
                running=self.jobs.running("policy"),
                error=self.jobs.errors.get("policy", ""),
                ready=self.policy_ready,
                action_at=self.action_at,
                now=now,
                timeout=self.timeout,
            )
        if not self.jobs.running("policy"):
            self.policy_ready = False
            if self.load_error in ("", "loading"):
                self.load_error = self.jobs.errors.get("policy", self.load_error)
        self.sequence += 1
        self.publisher.publish(
            OrinHeartbeat(
                stamp=self.get_clock().now().to_msg(),
                session=self.session,
                sequence=self.sequence,
                action_sequence=self.action_sequence,
                probe_id=self.probe_id,
                policy_active="policy" in self.jobs.children,
                degraded=bool(reason),
                reason=reason
                or ("policy running" if self.jobs.running("policy") else "standby"),
                policy_ready=self.policy_ready,
                policy_verified=self.policy_verified,
                bundle_id=self.bundle_id,
                load_error=self.load_error,
                preflight_passed=not bool(preflight),
                preflight_reason=preflight,
            )
        )

    def destroy_node(self):
        self.compute.close()
        self.offline.close()
        self.jobs.close()
        if self.recording is not None:
            self.recording.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = OrinSupervisor()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
