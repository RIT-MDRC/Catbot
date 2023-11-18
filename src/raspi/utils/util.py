import json
from gpiozero import InputDevice, OutputDevice
from control.muscle.muscle_controller import MuscleObj, add_muscle
from dotenv import dotenv_values
from io_controller.pneumatics.valve import add_valve_pin
from io_controller.pneumatics.pressure import add_pressure_pin
from utils.deviceMock import (
    DigitalOutputDeviceType,
    DigitalInputDeviceType,
    FakeInputDevice,
    FakeOutputDevice,
)
from utils.interval import set_interval


def is_dev() -> bool:
    """
    Check if the environment is set to development.

    :return: True if the environment is set to development, False otherwise
    """
    config = dotenv_values("src/raspi/.env")
    if config is None:
        raise ValueError("No config file found. Create a .env file in src/raspi")
    return config["ENV"] == "dev"


def create_input_device(pin: int, onDev: callable = None) -> DigitalInputDeviceType:
    """
    Create a new input device.

    :param pin: the pin number of the device
    :return: the device object
    """
    if is_dev():
        print("dev environment detected")
        print("mocking input device")
        obj = FakeInputDevice(pin)
        if onDev is not None:
            onDev(obj)
    else:
        obj = InputDevice(pin)
    return obj


create_pressure_device = lambda pin: create_input_device(pin, on_test_pressure_reading)
"""Create a new pressure device (alias for create_input_device)"""


def create_output_device(pin: int, onDev: callable = None) -> DigitalOutputDeviceType:
    """
    Create a new output device.

    :param pin: the pin number of the device
    :return: the device class
    """
    if is_dev():
        print("dev environment detected")
        print("mocking output device")
        obj = FakeOutputDevice(pin)
        if onDev is not None:
            onDev(obj)
    else:
        obj = OutputDevice(pin)
    return obj


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


def set_pin(config_data: dict, onDev: callable = None) -> dict:
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
            od = create_output_device(pin)
            add_valve_pin(key, od)
            ret[key] = od
        elif str.endswith(key, "pressure"):
            pin = config_data[key]
            id = create_pressure_device(pin)
            add_pressure_pin(key, id)
            ret[key] = id
        elif str.endswith(key, "muscle"):
            raw_muscle = set_pin(config_data[key])
            muscle = create_dataclass(MuscleObj(), raw_muscle)
            add_muscle(key, muscle)
            ret[key] = muscle
        elif str.endswith(key, "compressor"):
            pin = config_data[key]
            od = create_output_device(pin)
            ret[key] = od
        else:
            raise ValueError(f"Invalid key {key}")
    return ret


def on_test_pressure_reading(id):
    if isinstance(id, InputDevice) or isinstance(id, FakeInputDevice):

        def func():
            id.toggle()

        interval = set_interval(func, 5)
        return interval
