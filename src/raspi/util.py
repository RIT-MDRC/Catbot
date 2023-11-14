import json
from gpiozero import InputDevice, OutputDevice
from control.muscle.muscle_controller import MuscleObj, add_muscle

from io_controller.pneumatics.valve import add_valve_pin


def create_input_device(pin: int) -> InputDevice:
    """
    Create a new input device.

    :param pin: the pin number of the device
    :return: the device object
    """
    return InputDevice(pin)


create_pressure_device = create_input_device
"""Create a new pressure device (alias for create_input_device)"""


def create_output_device(pin: int) -> OutputDevice:
    """
    Create a new output device.

    :param pin: the pin number of the device
    :return: the device class
    """
    return OutputDevice(pin)


create_valve_device = create_output_device
"""Create a new valve device (alias for create_output_device)"""


def create_dataclass(dataclass: object, data: dict) -> object:
    for key in data.keys():
        k = key.split("_")[-1]
        dataclass[k] = key
    return dataclass


def get_pinconfig(filepath: str = "src/raspi/pinconfig.json") -> dict:
    """
    Get the pin configuration from a JSON file.

    :param filepath: the path to the JSON file
    :return: the pin configuration
    """
    with open(filepath, "r") as file:
        return json.load(file)


def set_pin(config_data: dict) -> dict:
    """
    Set the pin configuration.

    Args:
        config_data (dict): the pin configuration

    """
    ret = {}
    keys = config_data.keys()
    for key in keys:
        if str.endswith(key, "valve"):
            pin = config_data[key]
            od = create_valve_device(pin)
            add_valve_pin(key, od)
            ret[key] = od
        elif str.endswith(key, "pressure"):
            pin = config_data[key]
            id = create_pressure_device(pin)
            add_valve_pin(key, id)
            ret[key] = id
        elif str.endswith(key, "muscle"):
            raw_muscle = set_pin(config_data[key])
            muscle = create_dataclass(MuscleObj(), raw_muscle)
            add_muscle(key, muscle)
            ret[key] = muscle
        else:
            raise ValueError(f"Invalid key {key}")
