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

### Run script
Build the packages:
* `colcon build`
To run the UI package:
* `ros2 run ui ui`

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
