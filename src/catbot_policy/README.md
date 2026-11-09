# Catbot policy node

`catbot_policy` loads an exported actor on CPU, combines named feedback with
software-maintained observations, and publishes the existing
`catbot_interfaces/ActuatorPositionCommand`. It does not access CAN, initialize
foundation, or perform homing/calibration. A feedback provider is required;
hardware sensing and simulator feedback publishing are not implemented here.

## Pull the latest training policy

From this package directory:

```bash
cd src/catbot_policy  # from the hardware repository root
uv run pull_policy.py
```

The script uses your existing W&B login, `WANDB_ENTITY` (or your account's
default entity), and `WANDB_PROJECT` (default `catbot`). For first-time login or
a team project, run:

```bash
uv run pull_policy.py --login --entity YOUR_WANDB_ENTITY
```

It selects the newest run containing `config.json`, `model.xml`,
`manifest.json`, and a `model_N.pt` checkpoint, then downloads the highest
numbered checkpoint. Runs still training are eligible once these files have
been uploaded. To choose a specific run or checkpoint:

```bash
uv run pull_policy.py ENTITY/PROJECT/RUN_ID
uv run pull_policy.py ENTITY/PROJECT/RUN_ID model_1000.pt
```

uv installs the script's locked dependencies in a separate environment. No
training checkout, MuJoCo, mjlab, GPU, or ROS installation is needed for this
step. The script verifies the saved manifest, model checksum, configuration,
policy contract, and dependency versions before loading weights on CPU. It
uses RSL-RL's actor/export wrapper to preserve learned normalization, then
loads the resulting bundle through `PolicyRuntime` and checks inference parity.
Only use checkpoints from trusted W&B projects. Historical contracts, missing
manifests, and unsupported actor types fail explicitly.

Downloaded checkpoints and exported bundles are stored under
`~/.local/share/catbot/policies/ENTITY/PROJECT/RUN_ID/` (or under
`$XDG_DATA_HOME/catbot/policies`). Each successful preparation selects the bundle
through `catbot/policies/latest`; failed preparation keeps the previous
selection. Downloads refresh every time, and identical files reuse a validated
bundle. `source.json` beside the exported actor records the run, checkpoint,
and input checksums.

The launch file defaults to that selected bundle. In your **built and sourced
ROS workspace**, run:

```bash
ros2 launch catbot_policy catbot.launch.py
```

Pulling a policy does not start nodes or move hardware. Foundation and the policy
node start when you run the launch command, and a feedback provider is still
required. A running node keeps its loaded actor; restart it to load a newly
selected policy. You only need to build the launcher once; pulling another
policy does not require a rebuild. When using `--directory /custom/cache`, use
the explicit `policy_bundle:=...` launch command printed by the script.

## Export a policy

In the **catbot_mujoco** training checkout:

```bash
uv sync --locked
uv run --locked catbot-export-policy \
  --checkpoint /absolute/path/to/run/model_1000.pt \
  --output /absolute/path/to/deployment/bundle
```

The checkpoint directory must contain its saved `config.json`, `model.xml`, and
optional `manifest.json`. Existing training compatibility checks run before
loading trusted weights; historical 16-action checkpoints are rejected. Export
requires a new output directory and produces:

- `policy.pt`: deterministic TorchScript actor, including learned observation normalization.
- `policy.json`: bundle schema 1, policy contract 3, actuator ranges and order,
  control timestep, smoothing, gait settings, air-time limit, original model
  SHA-256, exported actor SHA-256, and PyTorch version.

Copy the entire bundle to the ROS machine. The runtime needs PyTorch 2.14.0,
but does not import the training checkout or simulator. TorchScript currently
emits upstream deprecation/Python 3.14 warnings; export and numerical parity
are covered by training tests. Only load bundles from trusted sources.

## Install and run (ROS Humble / Python 3.10)

In the **hardware** checkout, source ROS and use a system-Python virtual
environment so ROS's binary bindings remain available. Create the environment
only if this checkout does not already have a suitable one:

```bash
source /opt/ros/humble/setup.bash
uv venv --python /usr/bin/python3 --system-site-packages .venv
uv sync --locked --group policy
source .venv/bin/activate
python "$(command -v colcon)" build \
  --packages-select catbot_interfaces foundation catbot_policy \
  --cmake-args -DPython3_EXECUTABLE="$VIRTUAL_ENV/bin/python"
source install/setup.bash
ros2 run catbot_policy policy --ros-args \
  -p policy_bundle:=/absolute/path/to/deployment/bundle
```

Running colcon through the activated Python ensures the policy executable uses
the environment containing PyTorch. Linux uv installs select CPU PyTorch wheels.
The optional policy group is separate from `catbot setup`'s foundation runtime.
Do not use the IntelliSense-only ROS packages as runtime bindings. The Jazzy
devcontainer uses a different Python ABI; install this package's PyTorch
dependency in its native Python environment rather than reusing a Humble venv.

Parameters are `policy_bundle` (required), `mapping_file` (optional JSON), and
`feedback_timeout` (positive seconds, default `0.25`). Topic remapping works
through normal ROS arguments. For inspection without addressing foundation:

```bash
ros2 run catbot_policy policy --ros-args \
  -p policy_bundle:=/absolute/path/to/deployment/bundle \
  -r /body/control/position:=/policy/preview/position
ros2 topic echo /policy/preview/position
```

Run the echo in another sourced terminal. The node publishes nothing until
feedback arrives. Missing, malformed, non-finite, or stale feedback pauses
publication and freezes local history. The latest valid sample can be reused
until its timeout. Freshness uses local monotonic receipt time; `stamp` is
informational. Fresh feedback resumes existing history; restart the node when
starting a new feedback episode. Stopping publication leaves foundation's last
target in place; it does not idle motors.

### Launch foundation and policy together

Set `POLICY_BUNDLE` in [`launch/catbot.launch.py`](launch/catbot.launch.py) to the
exported bundle directory containing `policy.pt` and `policy.json`, then build
and source the workspace as above. Run:

```bash
ros2 launch catbot_policy catbot.launch.py
```

To select another bundle without editing the file:

```bash
ros2 launch catbot_policy catbot.launch.py \
  policy_bundle:=/absolute/path/to/another/bundle
```

Both nodes log to the terminal. Ctrl+C stops both; if either node exits, the
launch shuts down the other node too. Foundation performs its normal startup
calibration. The policy still needs a provider publishing `/policy/feedback`.
After changing the launch file, rebuild unless using a symlink install.

## Feedback and commands

Publish `catbot_interfaces/msg/PolicyFeedback` to `/policy/feedback` at the
policy rate or faster. Feedback uses best-effort, depth-one QoS. The saved
control interval is normally 0.02 seconds (50 Hz).

| Field | Size | Units / convention |
| --- | ---: | --- |
| `base_height_quaternion` | 5 | Height in meters, quaternion `(w,x,y,z)` |
| `heading_linear_velocity` | 3 | m/s in horizontal heading frame |
| `base_angular_velocity` | 3 | rad/s, body-local |
| `joint_positions` | 12 | Model coordinates, radians |
| `joint_velocities` | 12 | Model coordinates, rad/s |
| `normalized_air_time` | 4 | Swing duration / bundle `air_time_limit` |
| `previous_contact` | 4 | Contact booleans |
| `has_stance` | 4 | Whether stance has occurred during this episode |
| `motion_travel` | 12 | Absolute angular travel / usable joint range in the training window |
| `motion_progress` | 1 | Progress through the same motion-budget window |

Coordinates are +X forward, +Y left, +Z up. Joint order is FL, FR, RL, RR,
with abduction, flexion, knee within each leg; foot arrays are FL, FR, RL, RR.
Feedback is already in simulation/model coordinates. Hardware logical degrees
must be transformed by a future feedback provider. Providers maintain contact
history, normalized air time, and motion-window summaries coherently, following
the training environment's update order; the node does not estimate these.

Publish `geometry_msgs/msg/Twist` to `/policy/cmd_vel`:

```bash
ros2 topic pub --once /policy/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.2, y: 0.0}, angular: {z: 0.0}}'
```

`linear.x`, `linear.y`, and `angular.z` mean forward m/s, left m/s, and yaw
rad/s. Other components are ignored. The default command is zero; a received
command persists until replaced. Non-finite commands are rejected. Command and
actuator topics use reliable, depth-one QoS.

The node owns the remaining observations: command, previous smoothed normalized
action, previous action delta, and gait sine/cosine/blend. Histories and gait
phase/blend start at zero. Timing and gait transitions follow saved training
settings and advance once after each successful publication, without catch-up
for missed time. The contract remains 90 observations and 12 actions.

## Provisional actuator mapping

The bundled `catbot_policy/default_mapping.json` uses policy order:

```text
fla flf flk  fra frf frk  bla blf blk  bra brf brk
```

The action path clamps actor output to `[-1,1]`, applies saved exponential
smoothing, masks locked channels, and maps through saved actuator control
ranges. For each channel:

```text
model_radians = range_center + smoothed_action * range_half_width
logical_degrees = clamp(sign * degrees(model_radians) + offset, minimum, maximum)
```

Default signs are +1. Hip offsets are zero with ±40° limits; knee offsets
are +90° with ±55° limits. These are provisional signs and zeros, not physically
calibrated transforms. Clipping narrows the policy's simulated range and may
change behavior. Action history retains the smoothed normalized action before
hardware clipping, matching the training observation semantics.

Copy the JSON and set `mapping_file` to override names, signs, offsets, and
limits. All five arrays have 12 entries in policy order; names must be unique,
signs ±1, and finite minimum limits below maximum limits. Keep the configured
limits consistent with foundation's motion profiles. Foundation still owns
readiness checks, nonlinear knee linkage conversion, and motor inversion. The
node adds no simulated backlash or randomized command delay.

## Tests

Hardware-free runtime tests (Python 3.10):

```bash
uv sync --locked --group policy
.venv/bin/python -m unittest discover -s src/catbot_policy/test
```

To also run checkpoint download/export tests with RSL-RL installed for that
invocation, from the repository root:

```bash
uv run --group policy --with rsl-rl-lib==5.4.2 \
  python -m unittest discover -s src/catbot_policy/test
```

With real ROS bindings and generated interfaces available, the same command
also runs a ROS smoke test. It publishes synthetic feedback and velocity commands
to isolated test topics, receives remapped actuator targets, and checks that
publication stops on timeout. It never starts foundation or publishes to its
control topic. Without ROS, that test is explicitly skipped.
