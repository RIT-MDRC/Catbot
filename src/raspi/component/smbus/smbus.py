import logging

from smbus2 import SMBus
from state_management import create_generic_context, device_action, device_parser
from state_management.utils import FakeSMBus, is_dev

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
def write_byte(smbus2: SMBus, address, value, start_register=0x00) -> None:
    """
    Write a byte to the smbus2 device.

    Args:
        smbus2 (SMBus): the smbus2 device
        address (int): the address to write to
        value (list[int]): the value to write
        start_register (int): the register to start writing to
    """
    smbus2.write_byte(address, value)


@device_action(ctx)
def read_byte(smbus2: SMBus, address, start_register=0, length=2) -> int:
    """Read bytes from the smbus2 device.

    Args:
        smbus2 (SMBus): SMBus device to use
        address (int): I2C address of the device
        start_register (int): index of the register to start reading from
        length (int, optional): legnth of the data to read. Defaults to 1.

    Returns:
        int: data read from the device
    """
    return smbus2.read_i2c_block_data(address, start_register, length)[0]


@device_action(ctx)
def rdwr_i2c(smbus2: SMBus, *actions) -> list:
    """
    Write and read data from the smbus2 device.

    Args:
        smbus2 (SMBus): the smbus2 device
        address (int): the address to write to
        write_data (list[int]): the data to write
        read_length (int): the length of the data to read

    Returns:
        list: the data read from the device
    """
    smbus2.i2c_rdwr(*actions)
    return [list(action) for action in actions]
