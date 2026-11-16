"""Prepare current-contract training checkpoints without a simulator or ROS."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import shlex
import tempfile
from pathlib import Path

import torch

from catbot_policy.artifacts import (
    CHECKPOINT_PATTERN,
    DEFAULT_ENTITY,
    DEFAULT_PROJECT,
    NAME_PATTERN,
    RUN_FILES,
    available_models,
    checkpoint_name,
    policy_directory,
)
from catbot_policy.artifacts import (
    run_path as normalize_run_path,
)
from catbot_policy.files import sha256_file
from catbot_policy.protocol import OBSERVATION_DIMENSION
from catbot_policy.runtime import PolicyRuntime, validate_action, validate_metadata

SETTINGS = (
    "action_smoothing",
    "trot_speed",
    "bound_speed",
    "gait_transition_seconds",
    "air_time_limit",
)


def latest_checkpoint(files: dict) -> str | None:
    checkpoints = (
        (int(match[1]), name)
        for name in files
        if (match := CHECKPOINT_PATTERN.fullmatch(name))
    )
    return max(checkpoints, default=(None, None))[1]


def select_run(
    api, run_path: str | None, entity: str | None, project: str, checkpoint: str | None
):
    if run_path:
        run = api.run(run_path)
        files = {file.name: file for file in run.files()}
        name = checkpoint or latest_checkpoint(files)
        if name is None:
            raise ValueError(f"Run {run_path} has no model_N.pt checkpoints")
        missing = {*RUN_FILES, name} - files.keys()
        if missing:
            raise ValueError(f"Run {run_path} is missing: {', '.join(sorted(missing))}")
        return run_path, files, name

    entity = entity or api.default_entity
    if not isinstance(entity, str) or not NAME_PATTERN.fullmatch(entity):
        raise ValueError("Set WANDB_ENTITY or pass --entity")
    for run in api.runs(f"{entity}/{project}", order="-created_at"):
        files = {file.name: file for file in run.files()}
        name = latest_checkpoint(files)
        if name is not None and set(RUN_FILES) <= files.keys():
            path = f"{entity}/{project}/{run.id}"
            if not NAME_PATTERN.fullmatch(run.id):
                raise ValueError("W&B returned an invalid run ID")
            return path, files, name
    raise ValueError(f"No complete training runs found in {entity}/{project}")


def checkpoint_metadata(checkpoint: Path) -> tuple[dict, dict]:
    """Check the saved manifest before deserializing any checkpoint weights."""
    root = checkpoint.parent
    config = json.loads((root / "config.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported training manifest version")
    if "robot" not in config:
        raise ValueError("Checkpoint predates the 12-actuator policy; retrain it")
    if sha256_file(root / "model.xml") != manifest["model_sha256"]:
        raise ValueError("Saved model checksum does not match the training manifest")
    if any(config[key] != manifest[key] for key in ("environment", "robot", "runner")):
        raise ValueError("Saved configuration does not match the training manifest")
    versions = manifest["dependency_versions"]
    if versions["rsl-rl-lib"] != importlib.metadata.version("rsl-rl-lib"):
        raise ValueError(
            "Checkpoint RSL-RL version differs from the deployment exporter"
        )
    saved_torch = versions["torch"]
    if (
        not isinstance(saved_torch, str)
        or saved_torch.split("+")[0] != torch.__version__.split("+")[0]
    ):
        raise ValueError("Checkpoint and deployment PyTorch versions must match")
    metadata = {
        "schema_version": 1,
        "torch_version": torch.__version__.split("+")[0],
        "policy_sha256": "0" * 64,
        "model_sha256": manifest["model_sha256"],
        "policy_contract": manifest["policy_contract"],
        "settings": {name: config["environment"][name] for name in SETTINGS},
    }
    validate_metadata(metadata)
    return config, metadata


def export_checkpoint(checkpoint: Path, output: Path) -> Path:
    """Use RSL-RL's own actor/export wrapper, retaining learned normalization."""
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    config, metadata = checkpoint_metadata(checkpoint)
    actor_config = copy.deepcopy(config["runner"]["actor"])
    if actor_config.pop("class_name") != "MLPModel":
        raise ValueError("Only the current MLPModel actor is supported")
    if config["runner"]["obs_groups"]["actor"] != ["actor"]:
        raise ValueError("Unsupported actor observation groups")
    distribution = actor_config.get("distribution_cfg")
    if (
        distribution is not None
        and distribution["class_name"] != "GaussianDistribution"
    ):
        raise ValueError("Unsupported actor output distribution")

    from rsl_rl.models import MLPModel
    from tensordict import TensorDict

    torch.set_num_threads(1)
    observations = TensorDict(
        {"actor": torch.zeros(1, OBSERVATION_DIMENSION)}, batch_size=[1]
    )
    actor = MLPModel(observations, {"actor": ["actor"]}, "actor", 12, **actor_config)
    weights = torch.load(checkpoint, map_location="cpu", weights_only=True)
    actor.load_state_dict(weights["actor_state_dict"], strict=True)
    actor.eval()
    exported = torch.jit.script(actor.as_jit().cpu().eval())
    output.mkdir(parents=True)
    exported.save(str(output / "policy.pt"))
    metadata["policy_sha256"] = sha256_file(output / "policy.pt")
    (output / "policy.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Load through the same path as the ROS node and check deterministic parity.
    runtime = PolicyRuntime(output)
    generator = torch.Generator().manual_seed(0)
    with torch.inference_mode():
        for inputs in (
            torch.zeros(1, OBSERVATION_DIMENSION),
            torch.randn(1, OBSERVATION_DIMENSION, generator=generator) * 2 + 3,
        ):
            expected = actor(TensorDict({"actor": inputs}, batch_size=[1]))
            actual = runtime.actor(inputs)
            validate_action(actual)
            torch.testing.assert_close(actual, expected)
    return output


def prepare_policy(
    api,
    *,
    run_path=None,
    entity=None,
    project="catbot",
    checkpoint=None,
    directory=None,
) -> Path:
    run_path, files, checkpoint = select_run(api, run_path, entity, project, checkpoint)
    directory = (directory or policy_directory()).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    print(f"Selected {run_path} / {checkpoint}", flush=True)
    with tempfile.TemporaryDirectory(dir=directory, prefix=".download-") as temporary:
        staging = Path(temporary)
        names = (*RUN_FILES, checkpoint)
        for name in names:
            print(f"Downloading {name}", flush=True)
            files[name].download(root=str(staging), replace=True).close()
        hashes = {name: sha256_file(staging / name) for name in names}
        fingerprint = hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest()
        destination = directory.joinpath(
            *run_path.split("/"), f"{Path(checkpoint).stem}-{fingerprint}"
        )
        bundle = destination / "bundle"
        if destination.exists():
            PolicyRuntime(bundle)
        else:
            export_checkpoint(staging / checkpoint, staging / "bundle")
            (staging / "bundle/source.json").write_text(
                json.dumps(
                    {"run": run_path, "checkpoint": checkpoint, "sha256": hashes},
                    indent=2,
                )
                + "\n"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging.rename(destination)

    # A single selected-run link supplies both model files and the policy bundle.
    # This is a fixed local selection, not a W&B query at launch time.
    with tempfile.TemporaryDirectory(dir=directory, prefix=".select-run-") as temporary:
        selected = Path(temporary) / "selected"
        selected.symlink_to(destination, target_is_directory=True)
        selected.replace(directory / "selected")

    # Retain the existing bundle-only alias for older callers.
    with tempfile.TemporaryDirectory(dir=directory, prefix=".select-") as temporary:
        link = Path(temporary) / "latest"
        link.symlink_to("selected/bundle", target_is_directory=True)
        link.replace(directory / "latest")
    return bundle


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="?", help="RUN_ID or ENTITY/PROJECT/RUN_ID")
    parser.add_argument(
        "checkpoint",
        nargs="?",
        help="Checkpoint number or model_N.pt; omitted selects latest in this run",
    )
    parser.add_argument("--run-id", help="Alternative to positional RUN_ID")
    parser.add_argument(
        "--checkpoint",
        dest="checkpoint_number",
        help="Alternative checkpoint number or model_N.pt",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Explicitly select the newest complete W&B run",
    )
    parser.add_argument(
        "--entity", default=os.environ.get("WANDB_ENTITY", DEFAULT_ENTITY)
    )
    parser.add_argument(
        "--project", default=os.environ.get("WANDB_PROJECT", DEFAULT_PROJECT)
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=policy_directory(),
        help="Policy cache directory",
    )
    parser.add_argument(
        "--login", action="store_true", help="Log in to W&B before downloading"
    )
    args = parser.parse_args(argv)
    if args.run_id:
        if args.run:
            parser.error("Use either positional run or --run-id")
        args.run = args.run_id
    if args.checkpoint_number is not None:
        if args.checkpoint:
            parser.error("Use either positional checkpoint or --checkpoint")
        args.checkpoint = args.checkpoint_number
    if not args.run and not args.latest:
        parser.error("Specify RUN_ID for a fixed run, or explicitly use --latest")
    if args.run and args.latest:
        parser.error("Choose an explicit run or --latest, not both")
    try:
        if args.run:
            args.run = normalize_run_path(args.run, args.entity, args.project)
        if args.checkpoint:
            args.checkpoint = checkpoint_name(args.checkpoint)
    except ValueError as error:
        parser.error(f"{error}\n{available_models(args.directory)}")
    if not NAME_PATTERN.fullmatch(args.project):
        parser.error("project must be a W&B project name")
    if args.checkpoint and (
        not args.run or not CHECKPOINT_PATTERN.fullmatch(args.checkpoint)
    ):
        parser.error("checkpoint must be model_N.pt and requires an explicit run")

    import wandb

    try:
        if args.login:
            wandb.login()
        bundle = prepare_policy(
            wandb.Api(),
            run_path=args.run,
            entity=args.entity,
            project=args.project,
            checkpoint=args.checkpoint,
            directory=args.directory,
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        AssertionError,
        wandb.Error,
    ) as error:
        parser.exit(
            1,
            f"Policy preparation failed: {error}\n{available_models(args.directory)}\n",
        )
    print(f"run_directory: {bundle.parent}")
    print(f"policy_bundle: {bundle}")
    print(f"Selected local run: {args.directory.expanduser().resolve() / 'selected'}")
    print(f"Ready: {bundle}")
    print("Run in a built, sourced ROS workspace:")
    print(
        "  "
        + shlex.join(
            [
                "ros2",
                "launch",
                "catbot_policy",
                "catbot.launch.py",
                f"policy_bundle:={bundle}",
            ]
        )
    )


if __name__ == "__main__":
    main()
