import logging

from smbus2 import SMBus
from state_management import create_generic_context, device_parser
from state_management.utils import FakeSMBus, is_dev

from ...state_management.device import device_action

ctx = create_generic_context("smbus2", (SMBus, FakeSMBus))


@device_parser(ctx)
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


@device_action(ctx)
def write_byte(smbus2: SMBus, address, value) -> None:
    """
    Write a byte to the smbus2 device.

    Args:
        smbus2 (SMBus): the smbus2 device
        address (int): the address to write to
        value (int): the value to write
    """
    smbus2.write_byte(address, value)


@device_action(ctx)
def read_byte(smbus2: SMBus, address) -> int:
    """
    Read a byte from the smbus2 device.

    Args:
        smbus2 (SMBus): the smbus2 device
        address (int): the address to read from

    Returns:
        (int) the value read
    """
    return smbus2.read_byte(address)
