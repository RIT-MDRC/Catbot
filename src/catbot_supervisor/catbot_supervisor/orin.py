"""Orin service host: owns policy/jobs/telemetry and reports link facts to Pi."""

import json
import math
import time
import uuid

import rclpy
from catbot_policy.configuration import POLICY_DEFAULTS
from rclpy.node import Node
from std_msgs.msg import UInt64

from catbot_interfaces.msg import OrinHeartbeat, PolicyAction
from catbot_interfaces.srv import SupervisorJob
from catbot_supervisor.jobs import Jobs


class OrinSupervisor(Node):
    def __init__(self):
        super().__init__("orin_supervisor")
        self.policy_parameters = {
            name: self.declare_parameter(name, value).value
            for name, value in POLICY_DEFAULTS.items()
            if name not in ("action_session", "supervised_output", "simulation_mode")
        }
        self.timeout = float(self.declare_parameter("action_timeout", 0.25).value)
        self.lease_timeout = float(
            self.declare_parameter("pi_lease_timeout", 0.5).value
        )
        if not all(
            math.isfinite(v) and v > 0 for v in (self.timeout, self.lease_timeout)
        ):
            raise ValueError("Orin timeouts must be positive and finite")
        commands = json.loads(str(self.declare_parameter("jobs_json", "{}").value))
        if not isinstance(commands, dict) or "policy" in commands:
            raise ValueError("jobs_json must be an object; policy is reserved")
        self.session = uuid.uuid4().hex
        self.jobs = Jobs({**commands, "policy": self.policy_command()})
        self.probe_id = self.sequence = self.action_sequence = 0
        self.action_at = self.probe_at = None
        self.publisher = self.create_publisher(
            OrinHeartbeat, "/orin/supervisor/heartbeat", 1
        )
        self.create_subscription(UInt64, "/orin/supervisor/probe", self.probe, 1)
        self.create_subscription(PolicyAction, "/orin/policy/action", self.action, 1)
        self.create_service(SupervisorJob, "/orin/supervisor/job", self.job)
        self.create_timer(0.05, self.tick)

    def policy_command(self):
        command = ["ros2", "run", "catbot_policy", "policy", "--ros-args"]
        for name, value in {
            **self.policy_parameters,
            "action_session": self.session,
        }.items():
            command += ["-p", f"{name}:={json.dumps(value)}"]
        return command

    def probe(self, message):
        self.probe_id = message.data
        self.probe_at = time.monotonic()

    def action(self, message):
        if message.session == self.session and message.sequence > self.action_sequence:
            self.action_sequence = message.sequence
            self.action_at = time.monotonic()

    def job(self, request, response):
        try:
            now = time.monotonic()
            if request.start:
                if self.probe_at is None or now - self.probe_at > self.lease_timeout:
                    raise ValueError("No fresh Pi lease")
                if request.name == "policy" and not self.jobs.running("policy"):
                    if "policy" in self.jobs.children:
                        raise ValueError("Policy cleanup pending")
                    self.session = uuid.uuid4().hex
                    self.sequence = self.action_sequence = 0
                    self.action_at = None
                    self.jobs.commands["policy"] = self.policy_command()
                self.jobs.start(request.name)
            else:
                self.jobs.stop(request.name, now)
            response.success, response.message = (
                True,
                "accepted; heartbeat reports policy readiness",
            )
        except (ValueError, OSError) as error:
            response.success, response.message = False, str(error)
        return response

    def tick(self):
        now = time.monotonic()
        lease_lost = self.probe_at is None or now - self.probe_at > self.lease_timeout
        if lease_lost:
            for name in list(self.jobs.children):
                self.jobs.stop(name, now)
        self.jobs.tick(now)
        reason = ""
        if lease_lost:
            reason = "Pi probe lease expired"
        elif not self.jobs.running("policy"):
            reason = "policy job not running"
        elif self.action_at is None or now - self.action_at > self.timeout:
            reason = "policy action stream unavailable"
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
                reason=reason,
            )
        )

    def destroy_node(self):
        self.jobs.close()
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
