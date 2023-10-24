# Catbot CLI

Catbot CLI is a command line interface for Catbot. It allows you to interact with Catbot from the command line.

## Usage

To use the CLI, simply run the following command in the terminal:
```bash
catbot
```

## Commands

### `catbot --help`
Displays help information about the CLI.

### `catbot start`
Runs the main program in Raspberry Pi.

optional arguments:
* `-f`, `--file` - Path to the file containing the code to run. Defaults to `main` for `main.py`.
* `-D`, `--dev` - Runs the program in the current repo instead of the globally installed file.
### `catbot a <arduino-cli commands>`
Refaced arduino-cli


# Development Guide

### Setup Command
Catbot repo is made in a way such that anyone in the team can easily run catbot cli without setup.
However in order to do so, we need to bring the src folder outside of the user directory.
./src -> /opt/catbot/src
This is done by running the following command in the root directory of the repo during the postinstall script:
```bash
sudo npm install -g eslint --unsafe-perm=true --allow-root
```
> note: You must have sudo permission and npm installed in your system.
This also means that when ever you updated src folder, you need to run this command again to update the code to run for other members.

### Dev argument
Because of this globally installed script system what ever we write in the repo's src folder will not be run by other users.
But what if we want to test our code in the repo? We can use the `-D` or `-dev` argument to run the code in the repo.
```bash
catbot start -D
```
This will run the code in the repo instead of the globally installed code and will not require the postinstall script to be run.
You can also add the file argument to run a specific file in the repo.
```bash
catbot start -D -f destruct-inator
```
