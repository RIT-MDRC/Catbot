from dataclasses import dataclass

from smbus import smbus_actions
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
    _identifier: str
    i2c: smbus_actions.SMBus = identifier(smbus_actions.ctx)

    def read_data(self, register: int):
        """
        Get the degrees from the adc device.

        Args:
            register (int): the address of the device on the adc

        Returns:
            (float) the degrees
        """

        smbus_actions.write_byte(self.i2c, self.address, register)
        return smbus_actions.read_byte(self.i2c, self.address)


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
    adc = ADC(**config)
    for name, addr in adc.input_devices.items():
        register_device(
            analog_input_device_ctx,
            f"{adc._identifier}.{name}",
            ADCAnalogInputDevice(adc, addr),
        )
    return adc
