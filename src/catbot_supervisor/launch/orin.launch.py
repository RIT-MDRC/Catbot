"""Orin owns policy process lifetime and optional allowlisted jobs."""

from catbot_policy.configuration import POLICY_DEFAULTS
from catbot_supervisor.configuration import ORIN_DEFAULTS
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    defaults = {
        name: value
        for name, value in POLICY_DEFAULTS.items()
        if name not in ("action_session", "simulation_mode")
    }
    defaults.update(ORIN_DEFAULTS)
    return LaunchDescription(
        [
            *[
                DeclareLaunchArgument(
                    name,
                    default_value=str(value).lower()
                    if isinstance(value, bool)
                    else str(value),
                )
                for name, value in defaults.items()
            ],
            Node(
                package="catbot_supervisor",
                executable="orin",
                output="screen",
                parameters=[
                    {
                        name: ParameterValue(
                            LaunchConfiguration(name), value_type=type(value)
                        )
                        for name, value in defaults.items()
                    }
                ],
            ),
        ]
    )
