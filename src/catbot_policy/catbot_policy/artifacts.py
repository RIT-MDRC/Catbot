"""Local checkpoint selection and W&B naming; no ROS, Torch or network imports."""

import json
import re
from pathlib import Path

DEFAULT_ENTITY = "hiromon-rochester-institute-of-technology"
DEFAULT_PROJECT = "catbot"
NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
CHECKPOINT_PATTERN = re.compile(r"model_(\d+)\.pt")
RUN_FILES = ("config.json", "model.xml", "manifest.json")


def policy_directory():
    return Path(__file__).resolve().parents[1] / "artifacts"


def run_path(run_id, entity=DEFAULT_ENTITY, project=DEFAULT_PROJECT):
    if not isinstance(run_id, str):
        raise ValueError("Run must be a string")
    parts = run_id.split("/") if "/" in run_id else [entity, project, run_id]
    if len(parts) != 3 or any(
        not isinstance(p, str) or not NAME_PATTERN.fullmatch(p) for p in parts
    ):
        raise ValueError("Run must be a RUN_ID or ENTITY/PROJECT/RUN_ID")
    return "/".join(parts)


def checkpoint_name(value):
    value = str(value)
    if value.isascii() and value.isdecimal():
        return f"model_{int(value)}.pt"
    if CHECKPOINT_PATTERN.fullmatch(value):
        return value
    raise ValueError("Checkpoint must be a nonnegative number or model_N.pt")


def downloaded_models(directory):
    """Ignore incomplete/staged downloads; source.json records immutable identities."""
    models = []
    for source in sorted(
        Path(directory).expanduser().glob("*/*/*/model_*/bundle/source.json")
    ):
        try:
            data = json.loads(source.read_text())
            path = run_path(data["run"])
            name = checkpoint_name(data["checkpoint"])
            root = source.parent.parent
            if all(
                (root / name).is_file()
                for name in (*RUN_FILES, "bundle/policy.pt", "bundle/policy.json")
            ):
                models.append(
                    (path, int(CHECKPOINT_PATTERN.fullmatch(name)[1]), root.resolve())
                )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return models


def available_models(directory):
    models = downloaded_models(directory)
    lines = [f"  {run} checkpoint:={number} ({root})" for run, number, root in models]
    return "Downloaded models:\n" + ("\n".join(lines) if lines else "  (none)")


def resolve_downloaded(
    directory,
    run_id="",
    checkpoint="",
    *,
    entity=DEFAULT_ENTITY,
    project=DEFAULT_PROJECT,
):
    """No arguments retain selected; explicit run chooses highest LOCAL checkpoint."""
    directory = Path(directory).expanduser()
    try:
        if not run_id and not checkpoint:
            selected = (directory / "selected").resolve()
            if all(
                (selected / name).is_file()
                for name in (*RUN_FILES, "bundle/policy.pt", "bundle/policy.json")
            ):
                return selected
            raise ValueError(
                "No complete selected policy; download a run or pass run_id"
            )
        if not run_id:
            raise ValueError("checkpoint requires run_id")
        path = run_path(run_id, entity, project)
        matches = [m for m in downloaded_models(directory) if m[0] == path]
        if checkpoint:
            number = int(CHECKPOINT_PATTERN.fullmatch(checkpoint_name(checkpoint))[1])
            matches = [m for m in matches if m[1] == number]
        elif matches:
            number = max(m[1] for m in matches)
            matches = [m for m in matches if m[1] == number]
        if len(matches) != 1:
            reason = (
                "Not downloaded"
                if not matches
                else "Multiple exports match; use explicit paths"
            )
            raise ValueError(
                f"{reason}: {path}, checkpoint={checkpoint or 'highest local'}"
            )
        return matches[0][2]
    except ValueError as error:
        raise ValueError(f"{error}\n{available_models(directory)}") from error
