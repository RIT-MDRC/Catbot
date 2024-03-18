from dataclasses import dataclass

from smbus2 import SMBus
from state_management import (
    create_context,
    device,
    device_action,
    device_parser,
    identifier,
)


@device
@dataclass
class ADC:
    """
    Analog to Digital Converter
    """

    address: int
    i2c: SMBus = identifier("smbus2")


ctx = create_context("adc", ADC)


@device_parser(ctx)
def parse_adc(config):
    """
    Parse a new adc device.

    Args:
        address (int): the address of the device

    Returns:
        (ADC) the new adc device
    """
    return ADC(**config)


@device_action(ctx)
def get_degrees(device: ADC):
    """
    Get the degrees from the adc device.

    Args:
        device (ADC): the adc device

    Returns:
        (float) the degrees
    """
    return device.i2c.read_byte_data(device.address, 0)
