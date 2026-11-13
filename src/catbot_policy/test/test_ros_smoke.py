"""Exercise actual ROS messages when ROS is installed; never address foundation."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from test_runtime import feedback_values, make_bundle

try:
    import rclpy
    from catbot_policy.node import PolicyNode
    from geometry_msgs.msg import Twist
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.impl.implementation_singleton import rclpy_implementation  # noqa: F401
    from rclpy.qos import QoSProfile, ReliabilityPolicy

    from catbot_interfaces.msg import ActuatorPositionCommand, PolicyFeedback

    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


@unittest.skipUnless(
    ROS_AVAILABLE, "Requires real ROS bindings and generated interfaces"
)
class RosSmokeTests(unittest.TestCase):
    def test_feedback_to_remapped_actuator_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = make_bundle(Path(temporary))
            prefix = f"/policy_smoke_{os.getpid()}"
            rclpy.init(
                args=[
                    "--ros-args",
                    "-p",
                    f"policy_bundle:={bundle}",
                    "-r",
                    f"/body/control/position:={prefix}/output",
                    "-r",
                    f"/policy/feedback:={prefix}/feedback",
                    "-r",
                    f"/policy/cmd_vel:={prefix}/cmd_vel",
                ]
            )
            executor = SingleThreadedExecutor()
            policy = None
            probe = None
            try:
                policy = PolicyNode()
                probe = rclpy.create_node(
                    "policy_smoke_probe", use_global_arguments=False
                )
                executor.add_node(policy)
                executor.add_node(probe)
                received = []
                probe.create_subscription(
                    ActuatorPositionCommand, f"{prefix}/output", received.append, 1
                )
                feedback_pub = probe.create_publisher(
                    PolicyFeedback,
                    f"{prefix}/feedback",
                    QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
                )
                velocity_pub = probe.create_publisher(Twist, f"{prefix}/cmd_vel", 1)

                def spin_for(seconds):
                    deadline = time.monotonic() + seconds
                    while time.monotonic() < deadline:
                        executor.spin_once(timeout_sec=0.01)

                spin_for(0.3)
                self.assertEqual(received, [])
                feedback = PolicyFeedback()
                for name, value in feedback_values().items():
                    if name in ("previous_contact", "has_stance"):
                        value = [bool(item) for item in value]
                    setattr(feedback, name, value)
                velocity = Twist()
                velocity.linear.x = 0.8
                deadline = time.monotonic() + 5
                while (
                    not received or policy.command[0] < 0.7
                ) and time.monotonic() < deadline:
                    feedback_pub.publish(feedback)
                    velocity_pub.publish(velocity)
                    spin_for(0.03)
                self.assertTrue(received, "No actuator command received")
                self.assertAlmostEqual(policy.command[0], 0.8, places=5)
                self.assertEqual(
                    list(received[0].actuator_names), policy.mapping["actuator_names"]
                )
                self.assertEqual(len(received[0].positions_degrees), 12)
                self.assertGreater(received[0].positions_degrees[0], 0)
                spin_for(0.4)
                count = len(received)
                spin_for(0.1)
                self.assertEqual(
                    len(received), count, "Commands continued after feedback timeout"
                )
            finally:
                executor.shutdown()
                if policy is not None:
                    policy.destroy_node()
                if probe is not None:
                    probe.destroy_node()
                rclpy.shutdown()


if __name__ == "__main__":
    unittest.main()
