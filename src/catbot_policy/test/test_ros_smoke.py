"""Exercise actual ROS messages when ROS is installed; never address foundation."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures"


def feedback_values():
    return json.loads((FIXTURES / "contract.json").read_text())["feedback"]


def make_bundle(root):
    (root / "run_worker.py").touch()
    (root / "uv.lock").touch()
    return root


import pytest
import rclpy
from catbot_interfaces.msg import ActuatorPositionCommand, PolicyFeedback
from catbot_policy.node import PolicyNode
from geometry_msgs.msg import Twist
from rclpy.executors import SingleThreadedExecutor
from rclpy.impl.implementation_singleton import rclpy_implementation  # noqa: F401
from rclpy.qos import QoSProfile, ReliabilityPolicy


@pytest.mark.ros
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
                    "-p",
                    f"policy_worker_project:={bundle}",
                    "-p",
                    f"policy_uv_executable:={FIXTURES / 'fake_worker.py'}",
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
                self.assertNotEqual(received[0].positions_degrees[0], 0)
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
