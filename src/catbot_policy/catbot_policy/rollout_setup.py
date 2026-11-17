"""Align the separate CPU simulator with a downloaded training run."""

import json
import os
import re
import subprocess
from pathlib import Path


def find_rollout_repository():
    """Prefer the active workspace over a nested Catbot checkout's submodule."""
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for root in (start, *start.parents):
            repository = root / "external/catbot_sim_rollout"
            if (repository / "src/catbot_rollout/worker.py").is_file():
                return repository.resolve()
    return None


def prepare_rollout(repository: Path, run: Path):
    repository = repository.expanduser().resolve()
    if not (repository / "src/catbot_rollout/worker.py").is_file():
        raise ValueError(f"Not a rollout repository: {repository}")
    manifest = json.loads((run / "manifest.json").read_text())
    revision = manifest.get("git_revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise ValueError(
            "Training manifest needs a full git_revision for rollout setup"
        )
    if manifest.get("git_dirty"):
        print(
            "Warning: training used uncommitted changes; its revision may not fully reproduce it",
            flush=True,
        )

    project = repository / "pyproject.toml"
    lock = repository / "uv.lock"
    original_project = project.read_bytes()
    original_lock = lock.read_bytes() if lock.exists() else None
    # The rollout project declares this Git source as a single inline table.
    pattern = r'(?m)^(catbot-mujoco\s*=\s*\{[^\n]*\brev\s*=\s*")[^"]+("[^\n]*\})\s*$'
    updated, count = re.subn(
        pattern, lambda m: m[1] + revision + m[2], original_project.decode()
    )
    if count != 1:
        raise ValueError(f"Expected one catbot-mujoco Git revision in {project}")
    env = os.environ.copy()
    for name in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    environment = repository / ".venv"
    if environment.is_symlink():
        raise ValueError(
            f"Refusing to sync a symlinked simulator environment: {environment}"
        )
    env["UV_PROJECT_ENVIRONMENT"] = str(environment)
    print(
        f"Preparing simulator {environment} at training revision {revision}", flush=True
    )
    try:
        project.write_text(updated)
        for arguments in (("lock",), ("sync", "--locked")):
            subprocess.run(
                ["uv", *arguments, "--project", str(repository)], env=env, check=True
            )
        subprocess.run(
            [
                str(environment / "bin/python"),
                "-c",
                (
                    "import json,sys; from pathlib import Path; "
                    "from catbot.config import load_catbot_config; "
                    "load_catbot_config(json.loads(Path(sys.argv[1]).read_text())['environment'])"
                ),
                str(run / "config.json"),
            ],
            env=env,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        project.write_bytes(original_project)
        if original_lock is None:
            lock.unlink(missing_ok=True)
        else:
            lock.write_bytes(original_lock)
        raise RuntimeError(
            "Simulator preparation failed; dependency files restored and policy selection unchanged. "
            "Simulator .venv may have changed; rerun preparation before launching. "
            f"GPU .venv-cuda was not modified: {error}"
        ) from error
