# Catbot CLI

The Catbot CLI manages the project's uv environment and runs Catbot without
calling a system `python`, `python3`, or `pip` command directly.

## Install and set up

Install the CLI from the repository, then create its user-local environment:

```bash
npm install -g .
catbot setup
```

On an Ubuntu 22.04 Raspberry Pi with ROS Humble, `catbot setup` creates
`~/.local/share/catbot/.venv` from `/usr/bin/python3` so the apt-installed ROS
Python bindings remain ABI compatible. On macOS it uses uv-managed Python 3.10.
The command is safe to rerun after dependency updates.
On the Pi, setup also builds every ROS package discovered under the selected
Catbot project's `src/` directory, in dependency order. This includes
`catbot_interfaces`, `foundation`, `catbot_policy`, `catbot_supervisor`, and `ui`;
new packages under `src/` are picked up automatically. Build/install/log output
stays under `~/.local/share/catbot/ros` (or `$XDG_DATA_HOME/catbot/ros`).
Use `catbot setup --reset` only when the environment itself must be recreated.

For direct ROS commands after setup, source the CLI-managed overlay in that
terminal:

```bash
source /opt/ros/humble/setup.bash
source "${XDG_DATA_HOME:-$HOME/.local/share}/catbot/ros/install/setup.bash"
ros2 pkg prefix catbot_supervisor
```

Use `-D` or `--dev` with any command to run the current checkout rather than
the globally installed package:

```bash
catbot setup -D
```

## Commands

Start the ROS foundation node:

```bash
catbot start
```

On the Pi, `catbot start` sources ROS Humble and the user-local ROS overlay so
the generated messages and built packages are available. If the packages have
not been built, rerun `catbot setup`.

Run a sample:

```bash
catbot sample pneumatics/read_pgood
```

Run the interactive ODrive angle test:

```bash
catbot sample motor-test --motor odrive_1
```

Use a quoted `"*"` selector to make each interactive command apply to every
configured CAN axis:

```bash
catbot sample motor-test --motor "*"
```

The wildcard also works per command, such as `arm *`, `mp 15 *`, and `disarm *`.
Comma-separated motor names or axis IDs select a specific group, such as
`h 1,2,3`, `arm front_left,front_right`, or `mr -5 1,3`. Spaces after commas
are optional.

The test opens a full-screen terminal interface. Its scrollable command log is
above a focused input box. A status row below the input shows `CAN CHECKING`
while the interface starts, `CAN OK` when no configured axis reports an error,
or `CAN ERRORS (N)` when `N` configured axes report errors. Error transitions
write decoded per-axis details to the log. A compact command reference remains
visible next to the indicator.

The test starts with the motor disarmed. Enter commands in the bottom input,
use Up and Down to revisit commands from the current session, and explicitly
disarm when finished:

```text
> arm
> mp 15 0
> mr -5 0
> read
> disarm
```

The log and status continue updating during heartbeat waits. `q`, Ctrl-C, and
Ctrl-D stop the interface and request `IDLE` for every motor armed by the test.

`mp <angle> [motor]` commands an absolute logical joint angle. `mr <angle>
[motor]` adds a relative angle to the latest measured logical joint position.
For example, `mp 15 0` commands CAN axis 0 to 15 degrees, while `mr -5 0`
commands it 5 degrees back from its current position. Both commands reject a
final target outside the actuator's configured position bounds. The motor
selector may be omitted when the test was started with `--motor`.

`read [motor]` (or `r [motor]`) prints the latest encoder position as a homed
joint angle and raw motor turns. It is read-only and works while the motor is
disarmed. Use `read *` to read every configured motor.
If feedback cannot be converted to a joint angle (for example, a knee encoder
position outside the linkage geometry), the log shows the raw motor turns and
conversion error, and the session remains open.

`speed <degrees-per-second> [motor]` changes the trapezoidal trajectory speed
limit for later angle commands. For example, `speed 10 odrive_1` sets axis
`odrive_1` to 10 joint degrees per second, and `speed 10 *` applies it to every
configured motor. The setting is retained if that motor is subsequently armed.
It takes effect on the next `mp` or `mr` command; changing `speed` alone does not
replan a move already in progress. The argument is joint degrees per second.
For a nonlinear knee, it is converted using the current angle when `speed` is
issued; the resulting motor-turn limit stays fixed for subsequent moves and
rearming until another `speed` command changes it. A fixed motor-turn trajectory
gives an approximate joint speed that varies as the linkage angle changes,
with acceleration and deceleration at the start and end of a move.

`accel <motor-turns-per-second-squared> [motor]` (or `acceleration`) sets both
trajectory acceleration and deceleration. For example, `accel 0.5 blk` limits
both ramps to 0.5 motor turns/s² (180 motor degrees/s²). This uses raw motor
units for every profile, including knees. It accepts the same motor names,
axis IDs, comma lists, `*`, and launch default as `speed`. The setting applies
to the next position command and is retained through rearming for the session;
it does not change the shared profile or start motion.

`read-speed [motor]` (or `rs [motor]`) prints the latest measured encoder speed
in joint degrees per second and raw motor turns per second. It is read-only and
works while the motor is disarmed.
Conversion errors show the raw motor speed and keep the session open.

`arm [motor]` enters ODrive closed-loop position control only after checking for
reported errors. `disarm [motor]`, quitting, Ctrl-C, and EOF request the ODrive
`IDLE` state. Keep a physical emergency stop available; this software command is
not a substitute for removing motor power.

Use a different device configuration if needed:

```bash
catbot sample motor-test --motor odrive_1 --config /path/to/config.json
```

The CLI automatically sources `/opt/ros/humble/setup.bash` on the Pi and runs
Python files through the locked uv environment. Bring up `can0` separately
before running CAN samples.

Log retention keeps the latest five runs, including the current run. Foundation
and UI logs in `.log/` are pruned per program when logging starts, across log
levels. `catbot setup` also keeps the latest five Colcon build-log directories
under the Catbot runtime's `ros/log/` directory after each build. Older matching
logs are removed automatically; unrelated files and directories are preserved.
