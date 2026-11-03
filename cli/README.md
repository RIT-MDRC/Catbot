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

Run a sample:

```bash
catbot sample pneumatics/read_pgood
```

Run the interactive ODrive angle test:

```bash
catbot sample motor-test --motor odrive_1
```

Use a different device configuration if needed:

```bash
catbot sample motor-test --motor odrive_1 --config /path/to/config.json
```

The CLI automatically sources `/opt/ros/humble/setup.bash` on the Pi and runs
Python files through the locked uv environment. Bring up `can0` separately
before running CAN samples.
