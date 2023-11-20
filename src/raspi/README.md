# RASPBERRY PI CODE
## Description
This folder contains the code for the Raspberry Pi. The code is written in Python and is compiled using the Python interpreter.

## Short system description
The code is responsible for:
- TODO: update when implemented

## Pinconfig
The pinconfig is made for the purpose of configuring the pins of the Raspberry Pi easier and centralized into one location. 
The pinconfig.json is parsed as follows.
example:
```json
{
  "main_pressure": 17,
	"left_muscle": {
		"main_pressure": 27,
		"left_valve": 24
	},
	"main_compressor": 22
}
```
The type of object is determined by the key's ending in the dictionary.
If the name ends with "_muscle", the object represented is a muscle.
The following keys are currently supported:
- _pressure: the pin number of the pressure sensor
- _valve: the pin number of the valve
- _compressor: the pin number of the compressor
- _muscle: obj that represents the muscle should contain pressure and valve to work properly

### Note about pinconfig
- Although all the muscle is not specifically tied to a single pressure sensor it is still required to check for pressure. This is done so we can have the flexibility of the individual pressure system in the future.
- The pressure and valve does not have to be in the muscle object. It can be declared outside of it. However, if it is declared outside of the muscle object, and the muscle object references it inside with the same name. Which ever pin comes after will override the previously declared pin number. For example, main_pressure will be pin 27 instead of 17. Whether the pin number is already declared or not does not matter the number will always have to be declared.