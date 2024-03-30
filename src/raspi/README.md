# RASPBERRY PI CODE
## Description
This folder contains the code for the Raspberry Pi.

## structure
- [state_management](./state_management/README.md)
- [io_controller](./io_controller/README.md)
- [control](./control/README.md)
- [sample](./sample/README.md)
- [view](./view/README.md)


# DOCUMENTATION

## Description

Python code is separated into 3 different purposes:
### Test/Main Code (For Everyone)
### Components Code (For EE and SE)
### State Management (For SE)


## Setup Catbot
In order to run some of the commands mentioned below, you need to setup a few things. Don't worry you just need to download two things and you are good to go.

### 1. Install Node.js
Go to [Node.js](https://nodejs.org/en/download/) and download the LTS version of Node.js. This will help you install all of the dependencies required to run the commands even on your own computer. 

### 2. Install Python
Go to [Python](https://www.python.org/downloads/) and download the latest version of Python. This will help you run the python code on your computer.

### 3. Install VSCode
This is optional if you are comfortable with your own code editor. But if you are not, go to [VSCode](https://code.visualstudio.com/download) and download the latest version of VSCode. This will let you see the code and create your own sample code to test the hardware.

### 4. Install Git
You need to install git in order to copy the catbot source code to your own machine. Go to [Git](https://git-scm.com/downloads) and download the latest version of Git. This will let you clone the repository and run the code on your computer.

Now that you have installed all of the dependencies, you can setup your computer to run the code.

### 5. Copy the Catbot Source Code
Open your terminal and type:
```sh
git clone https://github.com/RIT-MDRC/Catbot.git CatbotCode
cd CatbotCode
```
This will copy the catbot source code to your computer. Now you can run the code on your computer.

### 6. Setup Catbot CLI
Once you have the source code, you need to setup the catbot cli. This will simplify the process of running the code on your computer. Type the following command in your terminal:
```sh
npm install -g
catbot --help
```
Now you can run catbot commands on your computer.

### 7. Run the python code on your computer!
Now that you have the source code and the catbot cli, you can run the code on your computer. 
If you want to learn more about Catbot CLI and how to run the code, go to [Catbot CLI](../../cli/README.md) documentation.

## Test/Main Code

This code is for testing mechanical/hardware functionality or for running the main code. This code is for everyone to use and look at.

files that include this code are:
- [main.py](./main.py)
- [sample](./samples/README.md)

[main.py](./main.py) is the main application code that runs the robot. You do not need to run this code unless you want to see the robot in action. 

[sample](./samples) is a directory that contains sample code that tests different parts of the hardware. You can run these code to test different parts of the hardware.
Go to your terminal and type:
```sh
cb sample dummySampleFile
```
to run the sample code on your computer or on catbot.

##