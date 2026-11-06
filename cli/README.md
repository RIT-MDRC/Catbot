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

The wildcard also works per command, such as `arm *`, `15 *`, and `disarm *`.
Comma-separated motor names or axis IDs select a specific group, such as
`h 1,2,3`, `arm front_left,front_right`, or `15 1,3`. Spaces after commas are
optional.

The test starts with the motor disarmed. At its prompt, explicitly arm it before
commanding an angle, and disarm it when finished:

```text
angle> arm
angle> 15
angle> disarm
```

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
