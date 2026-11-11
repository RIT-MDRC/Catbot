"""ROS adapter for the simulator-free policy runtime."""

from __future__ import annotations

import json
import resource
import time
from collections import deque
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from catbot_interfaces.msg import ActuatorPositionCommand, PolicyFeedback
from catbot_policy.runtime import FEEDBACK_FIELDS, PolicyRuntime


class PolicyNode(Node):
    """Wait for policy feedback and publish logical actuator position targets."""

    def __init__(self):
        super().__init__("catbot_policy")
        bundle = str(self.declare_parameter("policy_bundle", "").value)
        mapping = str(self.declare_parameter("mapping_file", "").value)
        timeout = float(self.declare_parameter("feedback_timeout", 0.25).value)
        if not bundle:
            raise ValueError("Set policy_bundle to an exported policy directory")
        self.runtime = PolicyRuntime(
            Path(bundle).expanduser(),
            Path(mapping).expanduser() if mapping else None,
            timeout,
        )
        reliable = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        feedback_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.simulation_mode = bool(
            self.declare_parameter("simulation_mode", False).value
        )
        self.contract_ready = not self.simulation_mode
        if self.simulation_mode:
            self.create_subscription(
                String,
                "/simulation/contract",
                self._contract_callback,
                QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
            )
        self.timing = deque(maxlen=10000)
        self.timing_started = time.monotonic()
        self.cpu_started = time.process_time()
        self.last_tick = None
        self.deadlines_missed = 0
        self.callback_overruns = 0
        self.metrics = self.create_publisher(String, "/policy/metrics", 1)
        self.create_timer(5.0, self._metrics)
        self.publisher = self.create_publisher(
            ActuatorPositionCommand, "/body/control/position", reliable
        )
        self.create_subscription(
            PolicyFeedback, "/policy/feedback", self._feedback_callback, feedback_qos
        )
        self.create_subscription(
            Twist, "/policy/cmd_vel", self._command_callback, reliable
        )
        self.create_timer(self.runtime.dt, self._tick)
        self.waiting = True
        self.last_error = None
        self.get_logger().info(
            f"Loaded policy ({self.runtime.dt:.4f}s interval); waiting for /policy/feedback"
        )
        self.get_logger().warning(
            "Joint signs, zeros, and limits use a provisional mapping; calibrate before hardware use."
        )

    def _contract_callback(self, message: String) -> None:
        value = json.loads(message.data)
        expected_mapping = self.runtime.mapping.metadata
        if (
            value.get("version") != 1
            or value.get("model_sha256") != self.runtime.metadata["model_sha256"]
            or value.get("policy_contract") != self.runtime.contract
            or value.get("settings") != self.runtime.settings
            or value.get("mapping") != expected_mapping
        ):
            raise ValueError(
                "Simulator model, policy contract, settings, or mapping mismatch"
            )
        self.contract_ready = True
        self.get_logger().info("Simulation contract verified")

    def _metrics(self):
        now = time.monotonic()
        elapsed = now - self.timing_started
        samples = list(self.timing)

        def percentiles(values):
            values = sorted(values)
            return {
                name: values[min(len(values) - 1, int((len(values) - 1) * q))]
                if values
                else None
                for name, q in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))
            }

        report = {
            "window_seconds": elapsed,
            "control_interval_ms": self.runtime.dt * 1000,
            "published_hz": len(samples) / elapsed,
            "inference_ms": percentiles([s[0] for s in samples]),
            "callback_ms": percentiles([s[1] for s in samples]),
            "feedback_age_ms": percentiles([s[2] for s in samples]),
            "missed_deadlines": self.deadlines_missed,
            "callback_overruns": self.callback_overruns,
            "cpu_percent_one_core": 100
            * (time.process_time() - self.cpu_started)
            / elapsed,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        self.metrics.publish(String(data=json.dumps(report)))
        self.timing.clear()
        self.deadlines_missed = 0
        self.callback_overruns = 0
        self.timing_started, self.cpu_started = now, time.process_time()

    def _feedback_callback(self, message: PolicyFeedback) -> None:
        if not self.contract_ready:
            return
        values = {name: getattr(message, name) for name, _ in FEEDBACK_FIELDS}
        try:
            self.runtime.update_feedback(values, time.monotonic())
        except (KeyError, ValueError) as error:
            self._report_error(f"Rejected policy feedback: {error}")

    def _command_callback(self, message: Twist) -> None:
        values = [message.linear.x, message.linear.y, message.angular.z]
        try:
            self.runtime.set_command(values)
        except ValueError as error:
            self._report_error(f"Rejected velocity command: {error}")

    def _publish(self, names: list[str], targets: list[float]) -> None:
        message = ActuatorPositionCommand()
        message.actuator_names = names
        message.positions_degrees = targets
        self.publisher.publish(message)

    def _report_error(self, message: str) -> None:
        if message != self.last_error:
            self.get_logger().error(message)
            self.last_error = message

    def _tick(self) -> None:
        if not self.contract_ready:
            return
        started = time.monotonic()
        if self.last_tick is not None:
            self.deadlines_missed += max(
                0, int((started - self.last_tick) / self.runtime.dt + 0.1) - 1
            )
        self.last_tick = started
        try:
            published = self.runtime.step(started, self._publish)
        except (ValueError, RuntimeError) as error:
            self._report_error(f"Policy inference failed: {error}")
            return
        if published:
            duration = time.monotonic() - started
            self.callback_overruns += int(duration > self.runtime.dt)
            self.timing.append(
                (
                    self.runtime.last_inference_seconds * 1000,
                    duration * 1000,
                    (started - self.runtime.feedback_received) * 1000,
                )
            )
            if self.waiting:
                self.get_logger().info(
                    "Feedback received; publishing actuator commands"
                )
            self.waiting = False
            self.last_error = None
        elif not self.waiting:
            self.get_logger().warning(
                "Feedback missing, invalid, or stale; pausing publication"
            )
            self.waiting = True


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = PolicyNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
