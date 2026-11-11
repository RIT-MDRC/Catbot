"""Launch foundation and a selected exported policy together."""

import os
from importlib.util import find_spec
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, Shutdown
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

# pull_policy.py selects this link after a successful download/export/load.
# Set this variable to another directory to choose a fixed policy instead.
POLICY_BUNDLE = str(
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    / "catbot/policies/latest"
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
                "policy_bundle",
                default_value=POLICY_BUNDLE,
                description="Exported policy directory containing policy.pt and policy.json",
            ),
            DeclareLaunchArgument(
                "backend", default_value="hardware", choices=["hardware", "simulation"]
            ),
            DeclareLaunchArgument(
                "mapping_file",
                default_value=str(
                    Path(find_spec("catbot_policy").origin).parent
                    / "default_mapping.json"
                ),
            ),
            Node(
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
                package="catbot_policy",
                executable="policy",
                output="screen",
                parameters=[
                    {
                        "policy_bundle": LaunchConfiguration("policy_bundle"),
                        "mapping_file": LaunchConfiguration("mapping_file"),
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
