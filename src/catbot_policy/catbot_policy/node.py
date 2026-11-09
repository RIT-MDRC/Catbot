"""ROS adapter for the simulator-free policy runtime."""

from __future__ import annotations

import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

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

    def _feedback_callback(self, message: PolicyFeedback) -> None:
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
        try:
            published = self.runtime.step(time.monotonic(), self._publish)
        except (ValueError, RuntimeError) as error:
            self._report_error(f"Policy inference failed: {error}")
            return
        if published:
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
