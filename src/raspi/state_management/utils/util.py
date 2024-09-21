import json
import logging
import os

from dotenv import dotenv_values
from gpiozero import DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice

from .deviceMock import (
    FakeDigitalInputDevice,
    FakeDigitalOutputDevice,
    FakePWMOutputDevice,
)
from .interval import set_interval


def is_dev() -> bool:
    """
    Check if the environment is set to development.

    :return: True if the environment is set to development, False otherwise
    """
    config_data = dotenv_values("src/raspi/.env")
    if config_data is None or config_data.get("ENV") is None:
        raise ValueError("No valid config file found. Create a .env file in src/raspi")
    return config_data.get("ENV") == "dev"


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
    else:
        obj = DigitalInputDevice(pin)
    return obj


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


def on_test_pressure_reading(id):
    if isinstance(id, DigitalInputDevice) or isinstance(id, FakeDigitalInputDevice):

        def func():
            id.toggle()

        interval = set_interval(func, 5)
        return interval
