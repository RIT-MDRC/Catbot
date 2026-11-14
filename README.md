<img src="https://pbs.twimg.com/profile_images/661962002/logo_400x400.png" align="right" alt="MDRC LOGO" title="MDRC LOGO" width="100">

# Catbot
Quadruped Hybrid Pneumatic-Electric Robot. Utilizes McKibben Muscles for bio-inpired locomotion.

## Setup

### Docker Dev Container
* Install [Docker](https://docs.docker.com/get-docker/)
* `ctrl+shift+p` -> `Dev Containers: Reopen in Container`

### Set up the Python environment

Install uv and use the Catbot CLI. On the Raspberry Pi this keeps ROS Humble's
system Python ABI while uv manages the project dependencies in a user-local
environment.

```bash
npm install -g .
catbot setup
```

For development from the current checkout, use `catbot setup -D` and pass `-D`
to later commands.

### Local macOS ROS IntelliSense

For editor completion and basic type checking without opening the ROS dev
container, install the optional IntelliSense-only dependency group:

```bash
uv sync --group ros-intellisense
uv run ty check
```

`rclpy-intellisense` and `common-interfaces-intellisense` are non-runtime
approximations of `rclpy` and common messages such as `std_msgs`. Do not execute
the ROS node against them; use the Jazzy devcontainer for `colcon build`, custom
generated interfaces, integration tests, and runtime validation. In VS Code,
select this checkout's `.venv/bin/python` interpreter after syncing the group.
Install the workspace-recommended `ty` and Ruff extensions when prompted. This
workspace disables Pylance and uses ty for completion, navigation, and type
diagnostics; the Microsoft Python extension remains enabled for interpreter and
debugger integration.

The ty source roots in `pyproject.toml` cover the ROS package directories and
Foundation's directly executed samples. The editor and CLI use these shared
paths without `PYTHONPATH` or `--extra-search-path` overrides.

### Run script
Build the packages:
* `colcon build`
To run the UI package:
* `ros2 run ui ui`

The UI publishes body-velocity commands to the policy. Its live ROS parameters
control command magnitude without changing the foundation motor-safety profile:

```bash
ros2 param set /ui_node speed_gain 0.5
ros2 param set /ui_node forward_speed_mps 0.2
ros2 param set /ui_node lateral_speed_mps 0.2
ros2 param set /ui_node command_acceleration_mps2 1.0
ros2 param set /ui_node fast_speed_multiplier 3.0
```

All values must be finite and positive. `speed_gain` scales both axes;
the forward and lateral parameters set their base speeds in meters per second.
`command_acceleration_mps2` limits the rate at which the two-dimensional body
velocity changes; stop commands remain immediate for safety. Changes apply to
the next UI command. These four primary motion values can also be edited in the
running UI's Motion settings panel.

The main foundation node exposes sparse body position control and all-motor
maintenance topics. See the [foundation body-control documentation](src/foundation/foundation/README.md#body-control-topics)
for message formats and publish examples.

The [policy node](src/catbot_policy/README.md) loads exported trained actors,
accepts named feedback on `/policy/feedback`, and publishes actuator targets.
Its documentation covers policy export, optional runtime dependencies, building,
topic remapping, and the provisional joint mapping.

To start foundation and policy together, build and source the workspace as
described in the policy documentation, then run:

```bash
ros2 launch catbot_policy catbot.launch.py
```

To download and prepare the latest W&B training checkpoint automatically:

```bash
cd src/catbot_policy
uv run pull_policy.py
```

The launcher uses the last successfully prepared bundle by default. You can
set `POLICY_BUNDLE` in
[`catbot.launch.py`](src/catbot_policy/launch/catbot.launch.py) to choose a fixed
bundle instead. See the
[policy setup instructions](src/catbot_policy/README.md#pull-the-latest-training-policy)
for W&B login, run selection, and ROS setup.

### Install dependencies
* install [uv](https://docs.astral.sh/uv/)
* install [nodejs](https://nodejs.org/en/download/)

### Install nodejs dependencies and catbot-cli
Run the following command in the terminal:
```bash
npm install -g .
catbot setup
```

For more command information goto [catbot-cli](cli/README.md)

## Contributing
### Before contributing
Make sure to read the documentation in the [wiki](https://github.com/RIT-MDRC/Catbot/wiki).
Questions with the documentation are welcomed in the [issues tab](https://github.com/RIT-MDRC/Catbot/issues).

## Shared simulation rollout worker

The rollout worker is the `external/catbot_sim_rollout` Git submodule, shared with
catbot-orin. Initialize the pinned checkout with:

```bash
git submodule update --init external/catbot_sim_rollout
```

It has its own uv project and pinned physics dependency. Only on a machine that
runs simulation, use `uv sync --locked --project external/catbot_sim_rollout`.
The Pi's policy/foundation environment does not need those dependencies.
See [the worker README](external/catbot_sim_rollout/README.md) for its CLI/protocol
and catbot-orin's `docs/SIMULATION.md` for distributed launch instructions.
