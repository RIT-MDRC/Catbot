"""Hardware launches the Pi gateway; simulation keeps its local policy path."""

import os
from importlib.util import find_spec
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from catbot_policy.configuration import POLICY_DEFAULTS, POLICY_PARAMETERS
from catbot_supervisor.rpi_configuration import RPI_DEFAULTS
from foundation.configuration import FOUNDATION_DEFAULTS
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, Shutdown
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

# pull_policy.py selects this link after a successful download/export/load.
# Set this variable to another directory to choose a fixed policy instead.
POLICY_BUNDLE = str(
    Path(find_spec("catbot_policy").origin).resolve().parents[1]
    / "artifacts/selected/bundle"
)


def generate_launch_description():
    # Foundation's modules currently use imports relative to its package directory.
    foundation_spec = find_spec("foundation")
    if foundation_spec is None or foundation_spec.origin is None:
        raise RuntimeError("Build and source the foundation package before launching")
    foundation_directory = str(Path(foundation_spec.origin).parent)
    python_path = os.pathsep.join(
        filter(None, [foundation_directory, os.environ.get("PYTHONPATH", "")])
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "backend", default_value="hardware", choices=["hardware", "simulation"]
            ),
            *[
                DeclareLaunchArgument(
                    name,
                    default_value=str(default).lower()
                    if isinstance(default, bool)
                    else str(default),
                )
                for name, default in {
                    **POLICY_DEFAULTS,
                    "policy_bundle": POLICY_BUNDLE,
                    "mapping_file": str(
                        Path(find_spec("catbot_policy").origin).parent
                        / "default_mapping.json"
                    ),
                }.items()
                if name != "simulation_mode"
            ],
            DeclareLaunchArgument("network_interface", default_value="eth0"),
            *[
                DeclareLaunchArgument(name, default_value=str(value))
                for name, value in {**RPI_DEFAULTS, **FOUNDATION_DEFAULTS}.items()
            ],
            DeclareLaunchArgument("hardware_config_file", default_value=""),
            DeclareLaunchArgument("protocol_config_file", default_value=""),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory("catbot_supervisor"),
                        "launch",
                        "rpi.launch.py",
                    )
                ),
                condition=IfCondition(
                    PythonExpression(
                        ["'", LaunchConfiguration("backend"), "' == 'hardware'"]
                    )
                ),
                launch_arguments={
                    "mapping_file": LaunchConfiguration("mapping_file"),
                    "network_interface": LaunchConfiguration("network_interface"),
                    **{
                        name: LaunchConfiguration(name)
                        for name in (
                            *RPI_DEFAULTS,
                            *FOUNDATION_DEFAULTS,
                            "hardware_config_file",
                            "protocol_config_file",
                        )
                    },
                }.items(),
            ),
            Node(
                condition=IfCondition(
                    PythonExpression(
                        ["'", LaunchConfiguration("backend"), "' == 'simulation'"]
                    )
                ),
                package="foundation",
                executable=PythonExpression(
                    [
                        "'simulation' if '",
                        LaunchConfiguration("backend"),
                        "' == 'simulation' else 'main'",
                    ]
                ),
                parameters=[{"mapping_file": LaunchConfiguration("mapping_file")}],
                output="screen",
                additional_env={"PYTHONPATH": python_path},
                on_exit=Shutdown(),
            ),
            Node(
                condition=IfCondition(
                    PythonExpression(
                        ["'", LaunchConfiguration("backend"), "' == 'simulation'"]
                    )
                ),
                package="catbot_policy",
                executable="policy",
                output="screen",
                parameters=[
                    {
                        **{
                            name: ParameterValue(
                                LaunchConfiguration(name),
                                value_type=type(POLICY_DEFAULTS[name]),
                            )
                            for name in POLICY_PARAMETERS
                            if name != "simulation_mode"
                        },
                        "simulation_mode": ParameterValue(
                            PythonExpression(
                                [
                                    "'",
                                    LaunchConfiguration("backend"),
                                    "' == 'simulation'",
                                ]
                            ),
                            value_type=bool,
                        ),
                    }
                ],
                on_exit=Shutdown(),
            ),
        ]
    )
