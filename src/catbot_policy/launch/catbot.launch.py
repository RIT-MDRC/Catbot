"""Launch foundation and a selected exported policy together."""

import os
from importlib.util import find_spec
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

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
            Node(
                package="foundation",
                executable="main",
                output="screen",
                additional_env={"PYTHONPATH": python_path},
                on_exit=Shutdown(),
            ),
            Node(
                package="catbot_policy",
                executable="policy",
                output="screen",
                parameters=[{"policy_bundle": LaunchConfiguration("policy_bundle")}],
                on_exit=Shutdown(),
            ),
        ]
    )
