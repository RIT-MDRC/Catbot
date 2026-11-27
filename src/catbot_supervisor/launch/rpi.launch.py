"""Pi hosts Foundation and decisions; no inference or job worker starts here."""

import json
import os
from importlib.util import find_spec
from pathlib import Path

from catbot_supervisor.rpi_configuration import RPI_DEFAULTS
from foundation.configuration import FOUNDATION_DEFAULTS
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
    hardware_path = Path(
        LaunchConfiguration("hardware_config_file").perform(context)
        or Path(spec.origin).parent / "pinconfig.json"
    ).expanduser()
    hardware = json.loads(hardware_path.read_text())
    axis_ids = [hardware["odrive_motor"][name]["axisID"] for name in names]
    board_axes = [
        hardware["odrive_motor"][name].get("controller_reboot_axis", axis & ~1)
        for name, axis in zip(names, axis_ids)
    ]
    python_path = os.pathsep.join(
        filter(None, [str(Path(spec.origin).parent), os.environ.get("PYTHONPATH", "")])
    )
    return [
        Node(
            package="foundation",
            executable="main",
            output="screen",
            additional_env={
                "PYTHONPATH": python_path,
                "CATBOT_PROTOCOL_CONFIG": LaunchConfiguration(
                    "protocol_config_file"
                ).perform(context),
            },
            parameters=[
                {
                    **{
                        name: float(LaunchConfiguration(name).perform(context))
                        for name in FOUNDATION_DEFAULTS
                    },
                    "hardware_config_file": str(hardware_path),
                }
            ],
            on_exit=Shutdown(),
        ),
        Node(
            package="catbot_supervisor",
            executable="rpi",
            additional_env={
                "CATBOT_PROTOCOL_CONFIG": LaunchConfiguration(
                    "protocol_config_file"
                ).perform(context)
            },
            output="screen",
            parameters=[
                {
                    "actuator_names": names,
                    "actuator_axis_ids": axis_ids,
                    "controller_reboot_axes": board_axes,
                    **{
                        name: float(LaunchConfiguration(name).perform(context))
                        for name in RPI_DEFAULTS
                    },
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
            *[
                DeclareLaunchArgument(name, default_value=str(value))
                for name, value in {**RPI_DEFAULTS, **FOUNDATION_DEFAULTS}.items()
            ],
            DeclareLaunchArgument("hardware_config_file", default_value=""),
            DeclareLaunchArgument("protocol_config_file", default_value=""),
            OpaqueFunction(function=nodes),
        ]
    )
