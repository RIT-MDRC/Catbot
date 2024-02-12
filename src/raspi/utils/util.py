import json
import logging

from control import muscle_actions
from dotenv import dotenv_values
from gpiozero import DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice
from io_controller import compressor_actions, pressure_actions, valve_actions
from utils.deviceMock import (
    FakeDigitalInputDevice,
    FakeDigitalOutputDevice,
    FakePWMOutputDevice,
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
    return config.get("ENV") == "dev"


def create_input_device(pin: int, onDev: callable = None):
    """
    Create a new input device.

    :param pin: the pin number of the device
    :return: the device object
    """
    if is_dev():
        logging.info("dev environment detected")
        logging.info("mocking input device for pin %s", pin)
        obj = FakeDigitalInputDevice(pin)
        if onDev is not None:
            onDev(obj)
    else:
        obj = DigitalInputDevice(pin)
    return obj


create_pressure_device = lambda pin: create_input_device(pin, on_test_pressure_reading)
"""Create a new pressure device (alias for create_input_device)"""


def create_output_device(pin: int, onDev: callable = None):
    """
    Create a new output device.

    :param pin: the pin number of the device
    :return: the device class
    """
    if is_dev():
        logging.info("dev environment detected")
        logging.info("mocking output device for pin %s", pin)
        obj = FakeDigitalOutputDevice(pin)
        if onDev is not None:
            onDev(obj)
    else:
        obj = DigitalOutputDevice(pin)
    return obj


def create_dataclass(dataclass: object, data: dict) -> object:
    for key in data.keys():
        k = key.split("_")[-1]
        dataclass[k] = key
    return dataclass


def create_pwm_device(pin: int, onDev: callable = None):
    """
    Create a new output device.

    :param pin: the pin number of the device
    :return: the device class
    """
    if is_dev():
        logging.info("dev environment detected")
        logging.info("mocking output device for pin %s", pin)
        obj = FakePWMOutputDevice(pin)
        if onDev is not None:
            onDev(obj)
    else:
        obj = PWMOutputDevice(pin)
    return obj


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
            valve_actions.register_valve(key, od)
            ret[key] = od
        elif str.endswith(key, "pressure"):
            pin = config_data[key]
            id = create_pressure_device(pin)
            pressure_actions.register_pressure(key, id)
            ret[key] = id
        elif str.endswith(key, "compressor"):
            pin = config_data[key]
            od = create_output_device(pin)
            compressor_actions.register_compressor(key, od)
            ret[key] = od
        elif str.endswith(key, "muscle"):
            raw_muscle = set_pin(config_data[key])
            muscle = create_dataclass(muscle_actions.MuscleObj(), raw_muscle)
            muscle_actions.register_muscle(key, muscle)
            ret[key] = muscle
        else:
            raise ValueError(f"Invalid key {key}")
    return ret


def on_test_pressure_reading(id):
    if isinstance(id, DigitalInputDevice) or isinstance(id, FakeDigitalInputDevice):

        def func():
            id.toggle()

        interval = set_interval(func, 5)
        return interval
