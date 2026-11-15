"""Launch foundation and a selected exported policy together."""

import os
from importlib.util import find_spec
from pathlib import Path

from catbot_policy.configuration import POLICY_DEFAULTS, POLICY_PARAMETERS
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, Shutdown
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
