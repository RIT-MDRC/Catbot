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
On the Pi, setup also builds the `catbot_interfaces` ROS message package.
Use `catbot setup --reset` only when the environment itself must be recreated.

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

On the Pi, `catbot start` sources ROS Humble and the user-local generated
interfaces so the custom body-control messages are available. If the interface
package has not been built, rerun `catbot setup`.

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
