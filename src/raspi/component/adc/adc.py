from dataclasses import dataclass

from smbus2 import SMBus
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


@device
@dataclass
class ADC:
    """
    Analog to Digital Converter
    """

    address: int
    i2c: SMBus = identifier("smbus2")
    input_devices: dict

    def __post_init__(self):
        for name, addr in self.input_devices.items():
            register_device(
                analog_input_device_ctx, name, ADCAnalogInputDevice(self, addr)
            )

    def read_data(self, register: int):
        """
        Get the degrees from the adc device.

        Args:
            register (int): the address of the device on the adc

        Returns:
            (float) the degrees
        """
        self.i2c.write_byte_data(self.address, register)
        return self.i2c.read_byte_data(self.address)


ctx = create_context("adc", ADC)


@device_parser(ctx)
def parse_adc(config: dict):
    """
    Parse a new adc device.

    Config:
    {
        address: int = i2c address of the adc
        i2c: SMBus = i2c object
        input_devices: {
            "name_of_device": int = address of the device on the adc
            ...
        }
    }
    """
    return ADC(**config)
