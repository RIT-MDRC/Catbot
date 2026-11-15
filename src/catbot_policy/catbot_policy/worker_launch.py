"""Shared uv worker launch configuration; safe to import on ROS Python."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerLaunchSpec:
    command: list
    environment: dict

    @staticmethod
    def resolve(device, project, environment, sync):
        """Resolve defaults without inspecting possibly remote filesystem paths."""
        cuda = str(device).startswith("cuda")
        if environment == "auto":
            environment = str(Path(project) / ".venv-cuda") if cuda else ""
        if sync == "auto":
            sync = not cuda
        elif isinstance(sync, str) and sync.lower() in ("true", "false"):
            sync = sync.lower() == "true"
        elif not isinstance(sync, bool):
            raise ValueError("Worker sync options must be auto, true or false")
        return environment, sync

    @classmethod
    def build(
        cls,
        project,
        uv,
        arguments,
        *,
        device="cpu",
        environment="",
        sync=True,
        python=None,
    ):
        project = Path(project).expanduser().resolve()
        environment, sync = cls.resolve(device, project, environment, sync)
        env = os.environ.copy()
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "VIRTUAL_ENV",
            "UV_PROJECT_ENVIRONMENT",
        ):
            env.pop(name, None)
        if environment:
            selected = Path(environment).expanduser().resolve()
            if not sync and not (selected / "bin/python").is_file():
                raise ValueError(
                    f"Prepare the worker environment at {selected} first, or select CPU. "
                    "Jetson CUDA needs a matching PyTorch build."
                )
            env["UV_PROJECT_ENVIRONMENT"] = str(selected)
        command = [
            uv,
            "run",
            "--locked" if sync else "--no-sync",
            "--project",
            str(project),
        ]
        if python:
            command += ["--python", python]
        command += ["python", *arguments, "--device", device]
        return cls(command, env)
