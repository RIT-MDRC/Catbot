import logging

from gpiozero import DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice
from smbus2 import SMBus
from state_management.device import create_generic_context, device_parser
from state_management.utils import (
    FakeDigitalInputDevice,
    FakeDigitalOutputDevice,
    FakePWMOutputDevice,
    is_dev,
)

from ..utils.deviceMock import FakeSMBus

__all__ = [
    "input_device_ctx",
    "output_device_ctx",
    "pwm_output_device_ctx",
]

input_device_ctx = create_generic_context(
    "input_device",
    (DigitalInputDevice, FakeDigitalInputDevice),
)
"""
Create a new input device component.
allowed device classes: DigitalInputDevice, FakeInputDevice
returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
"""


@device_parser(input_device_ctx)
def parse_input_device(config):
    """
    Parse a new input device.

    Args:
        pin_num (int): the pin number of the device

    Returns:
        (DigitalInputDevice) the new input device
    """
    if not isinstance(config, int):
        raise ValueError("Must be a pin number. Got " + str(config))
    if is_dev():
        logging.info(
            "dev environment detected. Mocking digital input device for pin %s", config
        )
        return FakeDigitalInputDevice(config)
    else:
        return DigitalInputDevice(config)


output_device_ctx = create_generic_context(
    "output_device", (DigitalOutputDevice, FakeDigitalOutputDevice)
)
"""
Create a new output device component.
allowed device classes: DigitalOutputDevice, FakeOutputDevice
returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
"""


@device_parser(output_device_ctx)
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
        logging.info(
            "dev environment detected. Mocking digital output device for pin %s", config
        )
        return FakeDigitalOutputDevice(config)
    else:
        return DigitalOutputDevice(config)


pwm_output_device_ctx = create_generic_context(
    "pwm_output_device", (PWMOutputDevice, FakePWMOutputDevice)
)


@device_parser(pwm_output_device_ctx)
def parse_pwm_output_device(config):
    """
    Parse a new pwm output device.

    Args:
        pin_num (int): the pin number of the device

    Returns:
        (PWMOutputDevice) the new pwm output device
    """
    if not isinstance(config, int):
        raise ValueError("Must be a pin number. Got " + str(config))
    if is_dev():
        logging.info(
            "dev environment detected. Mocking PWM output device for pin %s", config
        )
        return FakePWMOutputDevice(config)
    else:
        return PWMOutputDevice(config)


smbus2_ctx = create_generic_context("smbus2", (SMBus, FakeSMBus))


@device_parser(smbus2_ctx)
def parse_smbus2(config):
    """
    Parse a new smbus2 device.

    Args:
        bus_num (int): the bus number of the device

    Returns:
        (SMBus) the new smbus2 device
    """
    if not isinstance(config, int):
        raise ValueError("Must be a bus number. Got " + str(config))
    if is_dev():
        logging.info(
            "dev environment detected. Mocking smbus2 device for bus %s", config
        )
        return FakeSMBus(config)
    return SMBus(config)
