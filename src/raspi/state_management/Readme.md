# Core of the state management system
last updated: 2024-2-17
by @hiromon0125

## Description
The state management system allows us to code procedurally and functionally to keep all of the state in a central location making it easier to debug, visualize, and edit the hierarchy of the state. The state management system is built with decorators to make it easier to create new components. The key concept of the state management system is that the state is stored in a central dictionary that is used in each action method to grab the state of the component by their identifiers/keys and use the state. 

<details>

<summary>What is this style of code?</summary>

In many programming courses, the students are taught to use OOP to create programs, but OOP is not always the best solution for every problem. Due to the rigid structure in classes and behaviors using polymorphism and the Liskov Substitution Principle. For Catbot, we often found ourselves having to wipe a bunch of classes altogether to support a new electrical component that is built differently than the previous one; oftentimes done last minute before an exhibition. I (@hiromon0125) wondered why not make classes that can be reused. The problem is that making such a class structure is complex and difficult. Especially when we do not know where that change could happen in the future, it is hard to predict, and making every single class to be reusable is just not practical and triple in complexity with an enormous amount of classes. We also had numerous issues with Python's limited ability to support OOP techniques, so I (@hiromon0125) looked for an alternative solution to our problem and arrived at the best blend of Object-oriented, Procedural, and Functional programming. This state management system is built with techniques from all paradigms. Which resulted in the lowest coupling and highest cohesion in the code while also being explicit in the code. 
The OOP is used to declare the models used to describe the shape of the robot/hardware that are often just a struct and can be easily visualized within the pin config file. Procedural programming is used to declare the actions that can be called to change the state of the hardware. Making it easier than ever to write a small test function. Functional programming is used to abstract the link of the state to the actions. The majority of the code written for the state management system borrows many techniques from functional programming. 
The result is a state management system that is organized per component and integrated with a pin config file. The state management system is also very easy to test and debug and also protects unwanted access to private methods and variables in the classes. There are also many other benefits like omitting unused component stores and actions that can be called from any location; all a dev needs to do is import the action from the correct file and call the action. This allows us to easily integrate the state management system with any higher-level system like API or controllers.

</details>

# Methods

## create_generic_device_store()

This is the core method that initializes stores for all devices. This method is responsible for creating and storing the store for all devices. It checks for type errors and makes a method for registering the device to the store and a method for storing parsers of the device that the store is used for. The method is considered "generic" because it is the preferred method for creating masked devices from the generic devices (examples seen in the generic_devices folder). 

> [!WARNING]
> Non-generic devices should use the [`create_device_store`](create_device_store) method.

### Arguments
* generic_device_name: str
* device_classes: list
* parser_func: callable = None

### Description
* generic_device_name: The name of the component that the store is used for. This is used as a trigger for the pinconfig parser to use the device's parsing method(the first key in the pinconfig file).
* device_classes: A list of classes that the store is used for. This is used to check for type errors during registering devices after parsing.
* parser_func: This is one of two ways of handing the parsing method for a device into the state management system.

### Returns
* create_masked_device: callable[[str],(func: Any) -> Any]
* device_parser: callable[[dict], None]

> [!WARNING]
> The [`device_parser`](#device_parser) method should not exist outside of the file where it is initialized. Either use the `__all__` variable to protect the method or do not export the method in __init__.py. Violating this rule will result in an unexpected behavior.

<details>

<summary> Example </summary>

```py
create_output_device_component, _output_device_parser = create_generic_device_store(
    "output_device", (DigitalOutputDevice, FakeDigitalOutputDevice)
)

@_output_device_parser
def parse_output_device(config):
    """
    Parse a new output device.

    Args:
        pin_num (int): the pin number of the device

    Returns:
        (DigitalOutputDevice) the new output device
    """
    if not isinstance(config, int):
        raise ValueError("Must be a pin number. Got " + str(config))
    if is_dev():
        return FakeDigitalOutputDevice(config)
    else:
        return DigitalOutputDevice(config)
```

</details>

## device_parser()
Decorator returned by the [`create_generic_device_store`](#create_generic_device_store) method and [`create_device_store`](#create_device_store) method. This decorator is used to register the component's parsing method to be triggered by the pinconfig parser when it sees the parser's identifier(generic_device_name or device_name). 

### Arguments
* device_parser: `callable[[dict], Any]`

### Requirements of the decorated function:
- arguments: attribute (only the attributes of the device; not the entire config file)
- returns: the device state

<details>

<summary>Example usage of the decorated function</summary>

Let's say you have the following config file:
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
Then only the "1" or {"pressure": "left_pressure", "valve": "left_valve"} will be passed to the parser function.

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
</details>


## create_masked_device()
Decorator returned by the [`create_generic_device_store`](#create_generic_device_store) method. This method is used to create a renamed device component with an isolated store on runtime. 

### Arguments
* device_name: str

<details>

<summary>Description</summary>

* device_name: The name of the component that the store is used for. This is used as a trigger for the pinconfig parser to use the device's parsing method.

</details>

### Returns
* device_action: `callable[[str],(func: Any) -> Any]`

<details>

<summary>Example</summary>

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
</details>


## device_action()
Decorator returned by the [`create_device`](#create_masked_device) method and [`create_device_store`](#create_device_store) method. This method is used to decorate the action methods of the device such that the action method can be used with the device's identifier and the state management system will automatically grab the state of the device and pass it to the action method.

### Arguments
* func: callable

### Description
* func: The action method that is used to change the state of the device. The method is expected to take in a state as the first argument and the rest of the arguments are passed in. The method can return a new state or not. The decorator does not do any operation with the extra parameter or returned value. 

### Returns
* func: callable = decoarted function. 

<details>

<summary>Eample</summary>

```py
device_action = create_device("device_name")

@device_action
def set_state(state: stateClass, new_state: Any) -> stateClass:
    state.operate()
    return state
```
other examples can be found in valve.py or pressure.py

</details>


## create_device_store()

This is the main method for creating a store for any device. This method under the hood calls the [`create_generic_device_store`](#create_generic_device_store) method and returns the [`create_masked_device`](#create_masked_device) method and [`device_parser`](#device_parser) method. Use this to create non-generic devices.

### Arguments
* `device_name`: str
* `device_classes`: list
* `parser_func`: callable = None

<details>

<summary>Description</summary>

* `device_name`: The name of the component that the store is used for. This is used as a trigger for the pinconfig parser to use the device's parsing method.
* `device_classes`: A list of classes that the store is used for. This is used to check for type errors during registering devices after parsing.
* `parser_func`: This is one of two ways of handing the parsing method for a device into the state management system. You can use this instead of the [`device_parser`](#device_parser) decorator.

</detail>

### Returns
* `create_device`: callable[[str],(func: Any) -> Any]
* `device_parser`: callable[[dict], None]

<details>

<summary>Description</summary>

* `device_action`: a decorator for device actions. This is used to wrap a device action so that the device state is swapped with the state on runtime.
* `device_parser`: a decorator for device initializers that parses the config creates a new device instance and returns the device to be stored in the store. This parser function will be called during initialization for the application.

</details>

<details>

<summary>Example</summary>

```py
    device_action, device_parser = create_device_store("valve", [DigitalOutputDevice, FakeDigitalOutputDevice])

    @device_parser
    def parse_valve(config):
        if not isinstance(config, int):
            raise ValueError("Must be a pin number. Got " + str(config))
        if is_dev():
            return FakeDigitalOutputDevice(config)
        else:
            return DigitalOutputDevice(config)

    @device_action
    def turn_valve_on(valve: DigitalOutputDevice) -> None:
        valve.on()
```
</details>


## configure_device()

This method is used to configure the device with the pinconfig file. This method will parse the pinconfig file w/ file_kv_generator method and create the store for the device.

> [!NOTE]
> This method must be called before any script file runs to ensure that all of the devices are properly configured.

> [!WARNING]
> If the device's parser isn't registered in the global parser store, the method will skip the device and print a warning message. This could happen for two reasons. The device store was not initialized due to the file that the initializer is in was not imported in the script file(memory benefit), or the parser's identifier had a typo in the pinconfig file(Will need to be fixed immediately).

### Arguments
* file_name: str = "pinconfig.json"
* file_kv_generator: callable[[str], Generator[tuple[Any, Any], Any, None]] = open_json
