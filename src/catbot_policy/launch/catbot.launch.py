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
            DeclareLaunchArgument("policy_python", default_value="3.14"),
            DeclareLaunchArgument(
                "policy_worker_project",
                default_value=str(
                    Path(find_spec("catbot_policy").origin).parent / "inference"
                ),
            ),
            DeclareLaunchArgument("policy_uv_executable", default_value="uv"),
            DeclareLaunchArgument("feedback_timeout", default_value="0.25"),
            DeclareLaunchArgument("policy_worker_timeout", default_value="2.0"),
            DeclareLaunchArgument("policy_startup_timeout", default_value="120.0"),
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
                        "policy_python": ParameterValue(
                            LaunchConfiguration("policy_python"), value_type=str
                        ),
                        "policy_worker_project": LaunchConfiguration(
                            "policy_worker_project"
                        ),
                        "policy_uv_executable": LaunchConfiguration(
                            "policy_uv_executable"
                        ),
                        "feedback_timeout": ParameterValue(
                            LaunchConfiguration("feedback_timeout"), value_type=float
                        ),
                        "policy_worker_timeout": ParameterValue(
                            LaunchConfiguration("policy_worker_timeout"),
                            value_type=float,
                        ),
                        "policy_startup_timeout": ParameterValue(
                            LaunchConfiguration("policy_startup_timeout"),
                            value_type=float,
                        ),
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
