# Catbot CLI

Catbot CLI is a command line interface for Catbot. It allows you to interact with Catbot from the command line.

## Usage

To use the CLI, simply run the following command in the terminal:
```bash
catbot
```

## Commands overview

### `catbot --help`
Displays help information about the CLI.

### `catbot start`
Runs the main program in Raspberry Pi.

optional arguments:
* `-D`, `-dev` - Boolean - Runs the program in the current repo instead of the globally installed file.
  example: `catbot start -D` will result to running `./src/raspi/main.py` instead of `/opt/catbot/src/raspi/main.py`
* `-p`, `-proj` - String - Path to the project folder. Defaults to `src`.
  example: `catbot start -p Baby-inator` will result to running `Baby-inator/raspi/main.py` instead of `src/raspi/main.py`
* `-f`, `-file` - String - Path to the file containing the code to run. Defaults to `raspi/main` for `src/raspi/main.py`.
  example: `catbot start -f Landslideinator` will result to running `src/raspi/Landslideinator.py`

TL;DR: path is defined as `{-D}/{-p}/{-f}.py` default is `{"global-directory"}/{"src"}/{"raspi/main"}.py`

# Usage Guide

### Setup Command (npm install command)
**This is only for devs to deploy the command for other members of the team.**
Catbot repo is made in a way such that anyone in the team can easily run catbot cli without needing to setup any environment.
However in order to do so, we need to bring the src folder outside of the user directory.
./src -> /opt/catbot/src
This is done by running the following command in the root directory of the repo during the postinstall script:
```bash
sudo npm install -g
```
> note: You must have sudo permission and npm installed in your system.
This also means that when ever you updated src, you need to run this command again to update the code to run for other members.

### Dev argument
Because of this globally installed script system what ever we write in the repo's src folder will not be run by other users unless we run the npm install command.
But what if we want to test our code in the repo? We can use the `-D` or `-dev` argument to run the code in the current directory.
```bash
catbot start -D
```
This will run the code in the repo instead of the globally installed code and will not require the npm install command.
You can also add the file argument to run a specific file in the repo.
```bash
catbot start -D -f destruct-inator
```
runs `./src/destruct-inator.py` instead of `./src/raspi/main.py`

### Project argument
This cli also supports running code from the sister repository [Catbot-tools](https://github.com/RIT-MDRC/Catbot_Tools) where the file structure is a little bit different from this repo.
Tools file structure looks something like this 
```
.
├── Shrink-inator
│   ├── raspi
│   │   ├── main.py
│   │   └── ...
│   ├── arduino
│   │   ├── arduino.ino
│   │   └── ...
│   └── ...
├── DePandainator
│   ├── raspi
│   │   ├── main.py
│   │   └── ...
│   └── ...
└── ...
```
Which replaces our src folder with a named folder for each project. This is where the `-p` or `-proj` argument comes in.
```bash
catbot start -D -p Shrink-inator
```
This will run the code in `./Shrink-inator/raspi/main.py` instead of `./src/raspi/main.py`. Note the -D argument is required to run code in the other repo.