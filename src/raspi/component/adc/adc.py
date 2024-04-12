import logging
from dataclasses import dataclass

from component.smbus import smbus_actions
from smbus2 import i2c_msg
from state_management import (
    create_context,
    device,
    device_parser,
    identifier,
    register_device,
)


class ADCAnalogInputDevice:
    address: int

    def __init__(self, adc, address):
        """
        Address: int = address of the device on the adc (not including the adc address)
        adc: ADC = ADC object
        """
        self.adc = adc
        self.address = address

    @property
    def value(self):
        return self.adc.read_data(self.address)


analog_input_device_ctx = create_context("analog_input_device", (ADCAnalogInputDevice))


@device_parser(analog_input_device_ctx)
def parse_analog_input_device(config: dict):
    """
    Parse a new analog input device.

    Config:
    {
        adc: ADC = adc object
        address: int = address of the device on the adc
    }
    """
    return ADCAnalogInputDevice(**config)


@device
@dataclass
class ADC:
    """
    Analog to Digital Converter
    """

    address: int
    input_devices: dict
    power_down: int
    _identifier: str
    i2c: smbus_actions.SMBus = identifier(smbus_actions.ctx)

    def read_data(self, register: list):
        """
        Get the degrees from the adc device.

        :param register: list = register to read from
        :return: int = value read
        """
        print("{0:08b}".format(register))
        write = i2c_msg.write(self.address, register)
        read = i2c_msg.read(self.address, 1)
        return smbus_actions.i2c_rdwr(self.i2c, write, read)[1]


ctx = create_context("adc", ADC)


@device_parser(ctx)
def parse_adc(config: dict):
    """
    Parse a new adc device.

    Config:
    {
        address: int = i2c address of the adc
        i2c: SMBus = i2c object
        power_down: 0,1,2,3 = power down selection will be converted to 2 bit binary
        input_devices: {
            "name_of_device": int = channel of the device on the adc
            ...
        }
    }

    NOTE: Documentation for the logic explained here
    https://drive.google.com/open?id=1gvnOic5LwNqlCqx-z4vHShFm0rJplFgQ&disco=AAABJ0xEwNY
    """
    if config["power_down"] not in [0, 1, 2, 3]:
        raise ValueError(
            "Power down must be 0, 1, 2, or 3. Got " + str(config["power_down"])
        )
    config["address"] = convert_string_hex_to_int(config["address"])
    adc = ADC(**config)

    power_down = config["power_down"]  # 00, 01, 10, 11
    for name, addr in adc.input_devices.items():
        # 1 bit for Single-Ended/Differential Inputs and 3 channel bits
        register: int = 1 << 3 | channel_to_adc_addr(addr)
        register = (register << 2) | power_down  # 2 power down bits
        register = register << 2  # 2 unused bits
        analogDevice = ADCAnalogInputDevice(adc, register)
        register_device(
            analog_input_device_ctx, f"{adc._identifier}.{name}", analogDevice
        )
        logging.info(
            f"Created analog input device {name} with address {'{0:08b}'.format(register)}: {analogDevice}"
        )
    return adc


def channel_to_adc_addr(channel: int) -> int:
    """
    NOTE: channel will be mapped to the following due to the hardware:
    CH0 -> 000 (A0)
    CH1 -> 010 (A2)
    CH2 -> 100 (A4)
    CH3 -> 110 (A6)
    CH4 -> 001 (A1)
    CH5 -> 011 (A3)
    CH6 -> 101 (A5)
    CH7 -> 111 (A7)
    """
    if channel < 0 or channel > 7:
        raise ValueError("Channel must be between 0 and 7. Got " + str(channel))
    bit = channel % 4
    return bit << 1 | (channel // 4)


def convert_string_hex_to_int(hex_str: str) -> int:
    """
    Convert a string hex value to an int.

    :param hex_str: str = hex value
    :return: int = int value

    NOTE: hex_str can take "0x00" or "00", if "00" is passed base is taken from the second param in the int() function else it is automatically taken from the 0x prefix
    """
    return int(hex_str, 16)
