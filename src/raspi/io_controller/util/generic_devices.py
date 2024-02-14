from gpiozero import DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice
from utils.deviceMock import (
    FakeDigitalInputDevice,
    FakeDigitalOutputDevice,
    FakePWMOutputDevice,
)

from ...utils.util import is_dev
from .device import create_generic_device_store

create_input_device_component, input_device_parser = create_generic_device_store(
    "Input_Device",
    (DigitalInputDevice, FakeDigitalInputDevice),
)
"""
Create a new input device component.
allowed device classes: DigitalInputDevice, FakeInputDevice
returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
"""


@input_device_parser
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
        return FakeDigitalInputDevice(config)
    else:
        return DigitalInputDevice(config)


create_output_device_component, output_device_parser = create_generic_device_store(
    "output_device", (DigitalOutputDevice, FakeDigitalOutputDevice)
)
"""
Create a new output device component.
allowed device classes: DigitalOutputDevice, FakeOutputDevice
returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
"""


@output_device_parser
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


create_pwm_output_device_component, pwm_output_device_parser = (
    create_generic_device_store(
        "pwm_output_device", (PWMOutputDevice, FakePWMOutputDevice)
    )
)


@pwm_output_device_parser
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
        return FakePWMOutputDevice(config)
    else:
        return PWMOutputDevice(config)
