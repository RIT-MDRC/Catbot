"""Pi hosts Foundation and decisions; no inference or job worker starts here."""

import json
import os
from importlib.util import find_spec
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def nodes(context):
    mapping = Path(LaunchConfiguration("mapping_file").perform(context)).expanduser()
    names = json.loads(mapping.read_text())["actuator_names"]
    spec = find_spec("foundation")
    if spec is None or spec.origin is None:
        raise RuntimeError("Build and source Foundation before launching")
    python_path = os.pathsep.join(
        filter(None, [str(Path(spec.origin).parent), os.environ.get("PYTHONPATH", "")])
    )
    return [
        Node(
            package="foundation",
            executable="main",
            output="screen",
            additional_env={"PYTHONPATH": python_path},
            on_exit=Shutdown(),
        ),
        Node(
            package="catbot_supervisor",
            executable="rpi",
            output="screen",
            parameters=[
                {
                    "actuator_names": names,
                    "network_interface": LaunchConfiguration(
                        "network_interface"
                    ).perform(context),
                    "foundation_pid": int(
                        LaunchConfiguration("foundation_pid").perform(context)
                    ),
                }
            ],
            on_exit=Shutdown(),
        ),
    ]


def generate_launch_description():
    spec = find_spec("catbot_policy")
    if spec is None or spec.origin is None:
        raise RuntimeError("Build and source catbot_policy before launching")
    default_mapping = str(Path(spec.origin).parent / "default_mapping.json")
    return LaunchDescription(
        [
            DeclareLaunchArgument("mapping_file", default_value=default_mapping),
            DeclareLaunchArgument("network_interface", default_value="eth0"),
            DeclareLaunchArgument("foundation_pid", default_value="0"),
            OpaqueFunction(function=nodes),
        ]
    )
