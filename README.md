<img src="https://pbs.twimg.com/profile_images/661962002/logo_400x400.png" align="right" alt="MDRC LOGO" title="MDRC LOGO" width="100">

# Catbot
Quadruped Hybrid Pneumatic-Electric Robot. Utilizes McKibben Muscles for bio-inpired locomotion.

## Setup
### Install dependencies
* install [python](https://www.python.org/downloads/)
* install [nodejs](https://nodejs.org/en/download/)
* install [C/C++ extention](https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools) for VSCode
* install [Arduino extention](https://marketplace.visualstudio.com/items?itemName=vsciot-vscode.vscode-arduino) for VSCode
### Install python dependencies
Run the following command in the terminal:
```bash
pip install -r requirements.txt
```
for macos:
```bash
pip3 install -r requirements.txt
```
### Install nodejs dependencies and catbot-cli
Run the following command in the terminal:
```bash
npm -g install
catbot
```

For more command information goto [catbot-cli](cli/README.md)

### Setup Arduino Extension
* Open `src/arduino/arduino.ino` in VSCode
* Click on `Mac`, `Win32`, or `linux` on the bottom right corner of the window and change to `Arduino`
* Click on `<Select a Board Type>` in the bottom right corner
* Search `Arduino Nano`
* Select `Arduino Nano RP2040 Connect`
* Go to command pallet (`Ctrl+Shift+P`)
* Search `Arduino: Rebuild IntelliSense Configuration`

### Possible Errors on Setup
Include path error:
* Try editing the include path in `.vscode/c_cpp_properties.json`
* Click on `Quick Fix...` at the bottom of the error popup menu after hovering on the error
* Click on `Add to "include path": "..."`
* If the error occures with multiple include path options try adding them using the wildcard (`**`) operator
* Goto `.vscode.c_cpp_properties.json` in the root directory of the repo
* Example: `"includePath": ["${workspaceFolder}/**", "/Users/doofenshmirtz/Library/Arduino15/packages/arduino/hardware/mbed_nano/4.0.8/cores/arduino/mbed/**"]`