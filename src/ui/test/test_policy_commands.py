"""Hardware-free tests for UI policy direction commands."""

import sys
import types
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

UI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI_ROOT))

rclpy = cast(Any, types.ModuleType("rclpy"))
rclpy.init = Mock()
rclpy.shutdown = Mock()
rclpy.spin = Mock()
rclpy_node = cast(Any, types.ModuleType("rclpy.node"))
rclpy_node.Node = object
rclpy_parameter = cast(Any, types.ModuleType("rclpy.parameter"))


class Parameter:
    def __init__(self, name: str, *, value: float) -> None:
        self.name = name
        self.value = value


rclpy_parameter.Parameter = Parameter
sys.modules["rclpy"] = rclpy
sys.modules["rclpy.node"] = rclpy_node
sys.modules["rclpy.parameter"] = rclpy_parameter


class Vector3:
    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class Twist:
    def __init__(self) -> None:
        self.linear = Vector3()
        self.angular = Vector3()


geometry_msgs = types.ModuleType("geometry_msgs")
geometry_msgs_msg = cast(Any, types.ModuleType("geometry_msgs.msg"))
geometry_msgs_msg.Twist = Twist
sys.modules["geometry_msgs"] = geometry_msgs
sys.modules["geometry_msgs.msg"] = geometry_msgs_msg

from ui import main as ui_main


def test_publish_direction_maps_policy_twist_fields() -> None:
    node = object.__new__(ui_main.PublishInput)
    node.command_publisher = Mock()

    node.publish_direction(forward_mps=0.2, left_mps=-0.1, yaw_radps=0.3)

    message = node.command_publisher.publish.call_args.args[0]
    assert message.linear.x == 0.2
    assert message.linear.y == -0.1
    assert message.angular.z == 0.3


def test_direction_controller_maps_arrows_and_stop(monkeypatch) -> None:
    publisher = Mock()
    monkeypatch.setattr(ui_main, "pub_node", publisher)

    ui_main.DirectionController.up()
    publisher.publish_command.assert_called_with(1.0, 0.0, fast=False)
    ui_main.DirectionController.left()
    publisher.publish_command.assert_called_with(0.0, 1.0, fast=False)
    ui_main.DirectionController.right()
    publisher.publish_command.assert_called_with(0.0, -1.0, fast=False)
    ui_main.DirectionController.down()
    publisher.publish_command.assert_called_with(-1.0, 0.0, fast=False)
    ui_main.DirectionController.stop()
    publisher.stop.assert_called_once_with()


def test_publish_command_applies_live_speed_parameters() -> None:
    node = object.__new__(ui_main.PublishInput)
    node.publish_direction = Mock()
    values = {
        "forward_speed_mps": 0.3,
        "lateral_speed_mps": 0.2,
        "speed_gain": 0.5,
        "fast_speed_multiplier": 2.0,
        "command_acceleration_mps2": 1.0,
    }
    node.get_parameter = Mock(
        side_effect=lambda name: SimpleNamespace(value=values[name])
    )
    node.last_velocity = (0.0, 0.0)
    node.last_velocity_time = monotonic() - 1.0

    node.publish_command(1.0, -1.0, fast=True)

    node.publish_direction.assert_called_once_with(0.3, -0.2)


def test_update_motion_settings_updates_live_ros_parameters() -> None:
    node = object.__new__(ui_main.PublishInput)
    node.set_parameters = Mock(
        return_value=[SimpleNamespace(successful=True, reason="")] * 4
    )

    node.update_motion_settings(0.4, 0.25, 0.75, 1.5)

    parameters = node.set_parameters.call_args.args[0]
    assert {parameter.name: parameter.value for parameter in parameters} == {
        "forward_speed_mps": 0.4,
        "lateral_speed_mps": 0.25,
        "speed_gain": 0.75,
        "command_acceleration_mps2": 1.5,
    }
