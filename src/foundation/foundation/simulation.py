"""Foundation simulation transport. Never imports or initializes hardware."""

import json
import math
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

from catbot_interfaces.msg import ActuatorPositionCommand


class SimulationFoundation(Node):
    def __init__(self):
        super().__init__("foundation_node")
        path = str(self.declare_parameter("mapping_file", "").value)
        if not path:
            raise ValueError("Simulation foundation requires mapping_file")
        self.mapping = json.loads(Path(path).expanduser().read_text())
        names = self.mapping["actuator_names"]
        if (
            len(names) != 12
            or any(not isinstance(n, str) or not n.strip() for n in names)
            or len(set(names)) != 12
        ):
            raise ValueError("Expected 12 unique actuator names")
        self.limits = dict(
            zip(
                names,
                zip(
                    self.mapping["minimum_degrees"],
                    self.mapping["maximum_degrees"],
                    strict=True,
                ),
                strict=True,
            )
        )
        if len(self.limits) != 12 or any(
            not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi
            for lo, hi in self.limits.values()
        ):
            raise ValueError("Invalid mapping limits")
        self.publisher = self.create_publisher(
            ActuatorPositionCommand, "/simulation/control/position", 1
        )
        self.create_subscription(
            ActuatorPositionCommand, "/body/control/position", self.accept, 1
        )
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.status = self.create_publisher(String, "/foundation/backend", qos)
        self.status.publish(String(data="simulation"))
        self.get_logger().info("Simulation backend active; hardware is not initialized")

    def accept(self, message):
        names, positions = message.actuator_names, message.positions_degrees
        if not names or len(names) != len(positions) or len(set(names)) != len(names):
            self.get_logger().error("Rejected malformed simulation actuator command")
            return
        for name, value in zip(names, positions, strict=True):
            bounds = self.limits.get(name)
            if (
                bounds is None
                or not math.isfinite(value)
                or not bounds[0] <= value <= bounds[1]
            ):
                self.get_logger().error(
                    "Rejected unknown, non-finite, or out-of-bounds actuator target"
                )
                return
        self.publisher.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = SimulationFoundation()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
