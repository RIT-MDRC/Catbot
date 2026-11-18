# Catbot runtime

## Ownership and downstream consumers

This repository owns Foundation hardware/body control, ROS interfaces, UI, and
policy deployment/inference. The sibling `catbot_mujoco` repository produces the
training checkpoints and model/configuration consumed by `src/catbot_policy`.
`catbot-orin` consumes a pinned copy of this repository at `external/Catbot`.
That submodule and a sibling `catbot` directory are separate working trees;
changes to one do not update the other.

## Implementation boundaries

- Keep ROS adapters on the Python ABI of the target ROS distribution (Humble CI
  uses Python 3.10). Root dependencies use their own Python 3.10 uv project;
  policy tests and CPU inference have separate Python 3.14 projects. Jetson CUDA
  inference uses its separately provisioned environment. Keep their locks separate.
- Call Foundation component actions by registered name and use narrow getters.
  Consumer code must not access component `.ctx.store`. Preserve required
  import-time parser registration and per-axis motion/fault validation.
- Preserve observation/action order, units, smoothing and history timing,
  learned normalization, model hashes, and compatibility checks. Intentional
  incompatible interfaces require coordinated versioning and checkpoint handling.
- `tests/fixtures/contract.json` is the authoritative golden contract; Orin reads
  it through its pinned submodule. Change it only with an intended semantic change
  and assertions that establish the new behavior.
- Policy/foundation simulation uses the separately pinned
  `external/catbot_sim_rollout` project. Do not assume it imports the sibling
  training working tree or requires its dependencies in the Pi environment.

## Required verification

Read `.github/workflows/policy.yml` and `tests/README.md` before changing code.
Run its complete required checks for changes, including downstream checks when
shared interfaces change. The workflow is authoritative for commands and floors:

- `unit`: the listed Foundation/UI behavioral tests using the root uv project,
  then the full non-ROS policy suite using `uv run --locked --project tests`.
  Enforce coverage separately for `runtime.py` (92%) and `deployment.py` (90%).
- `ros`: build generated interfaces and the policy adapter in ROS Humble, then
  run the required ROS smoke test with pytest plugin autoload disabled.

Do not weaken checks, lower floors, or silently skip ROS tests to obtain a pass.
For Foundation changes also use the configured `ty` and Ruff checks on affected
files; distinguish those from the workflow's required jobs.
If an environment is unavailable, name the exact unverified check and blocker.
CPU tests do not establish hardware calibration, CUDA parity, or physical behavior.

For cross-project compatibility validation, use the `catbot-workspace` skill when
available. When publication is in scope, publish a Catbot commit before updating
Orin's gitlink to it, and verify CI on the final published commits and pins.
