# Core of the state management system

## Description
The state management system allows us to code procedurally and functionally to keep all of the state in a central location making it easier to debug, visualize, and edit the heirarchy of the state. The state management system is built with decorators to make it easier to create new components. The key concept of the state management system is that the state is stored in a central dictionary that is used in each action methods to grab the state of the component by their identifiers/keys and use the state. 

## What is this style of code?
In many programming courses, the students are taught to use OOP to create a program and OOP is not always the best solution for every problem especially with the idea of regid structure in classes and behaviors using polymorphism and Liskov Substitution Principle. For catbot we often found ourselves having to wipe a bunch of classes all together to support a new electrical component that is built differently than the previous one often done last minute before a fair. I (@hiromon0125) wondered why not make classes that can be reused? The problem is that making such class structure are complex and difficult. Especially when we do not know where that change could happen in the future. It is hard to predict and making every single class to be reusable is just not practical and triple in complexity with enormous amount of classes. We also had numerous issue with python's limited ability to support OOP techniques, so I (@hiromon0125) looked for an alternative solution to our problem and arrived to the best blend of Object oriented, Procedural, and Functional programming. This state management system is built with this blend in mind. Which resulted in the lowest coupling and highest cohesion in the code. 
The OOP is used to declare the models used to describe the shape of the robot/hardware that are often just a struct and can be easily visualized within the pinconfig file. The procedural programming is used to declare the actions that can be called to change the state of the hardware. Making it easier than ever to write a small test function. The functional programming is used to abstract the link of the state to the actions. Majority of the code written for the state management system borrows many techniques from functional programming. 

# Methods

## create_generic_device_store()

This is the core method that initializes stores for all devices. This method is responsible for creating and storing the store for all devices. It checks for type errors and make method for registering device to the store, and a method for storing parsers of the device that the store is used for. The method is considered "generic" because it is the preferred method for creating generic devices (examples seen in the generic_devices folder). Non-generic devices can be created using the `create_device_store` method.

### Arguments
* generic_device_name: str
* device_classes: list
* parser_func: callable = None

### Description
* generic_device_name: The name of the component that the store is used for. This is used as a trigger for the pinconfig parser to use the device's parsing method.
* device_classes: A list of classes that the store is used for. This is used to check for type errors during registering devices after parsing.
* parser_func: This is one of two ways of handing the parsing method for a device into the state management system.

### Returns
* create_device_component: callable[[str],(func: Any) -> Any]
* device_parser: callable[[dict], None]

### Usage
See declaration of [create_input_device_component](https://github.com/RIT-MDRC/Catbot/blob/888e1786e610cc93e432e9931fccfee7f48a3408/src/raspi/state_management/generic_devices/generic_devices.py#L17)



## device_parser()
Decorator returned by the `create_generic_device_store` method. This method is used to register component's parsing method to be triggerred by the pinconfig parser when it sees the component's name. 

### Arguments
* device_parser: `callable[[dict], Any]`

### Requirements of the decorated function:
- arguments: attribute (only the attributes of the device; not the entire config file)
- returns: the device state

### Example of the decorated function:

Lets say you have the following config file:
```json
{
    "valve": {
        "left_valve": 1
    },
    "muscle": {
        "left_muscle": {
            "pressure": "left_pressure",
            "valve": "left_valve"
        }
    }
}
```
Then only the "1" or {"pressure": "left_pressure","valve": "left_valve"} will be passed to the parser function.

Example:
```py
@device_parser
def parse_valve(attribute: int):
    if not isinstance(attribute, int):
        raise ValueError("Must be a pin number. Got " + str(attribute))
    if is_dev():
        return FakeDigitalOutputDevice(attribute)
    else:
        return DigitalOutputDevice(attribute)
```


## create_device_component()
Decorator returned by the `create_generic_device_store` method. This method is used to create a renamed device component with an isolated store on runtime. 

### Arguments
* device_name: str

### Description
* device_name: The name of the component that the store is used for. This is used as a trigger for the pinconfig parser to use the device's parsing method.

### Returns
* device_action: `callable[[str],(func: Any) -> Any]`

### Usage:
```py
valve_action, valve_parser = create_output_device_component("valve")
# 'create_output_device_component' is the variable to this function call first 
# initialized by the generic device store.

@valve_parser
def parse_valve(arribute: int):
    if not isinstance(arribute, int):
        raise ValueError("Must be a pin number. Got " + str(arribute))
    if is_dev():
        return FakeDigitalOutputDevice(arribute)
    else:
        return DigitalOutputDevice(arribute)

@valve_action
def turn_valve_on(valve: DigitalOutputDevice) -> None:
    valve.on()
```

## device_action()
Decorator returned by the `create_device_component` method. This method is used to decorate the action methods of the device such  that the action method can be used with the device's identifier and the state management system will automatically grab the state of the device and pass it to the action method.

### Arguments
* func: callable

### Description
* func: The action method that is used to change the state of the device. The method is expected to take in a state as the first argument and the rest of the arguments are passed in. The method can return a new state or not. The decorator does not do any operation with extra parameter or returned value. 

### Returns
* func: callable = decoarted function. 

### Usage example
```py
device_action = create_device_component("device_name")

@device_action
def set_state(state: stateClass, new_state: Any) -> stateClass:
    state.operate()
    return state
```
other examples can be found in valve.py or pressure.py