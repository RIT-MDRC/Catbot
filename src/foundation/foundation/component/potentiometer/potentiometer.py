from dataclasses import dataclass

from component.adc import adc_actions
from .pin import analog_pin_actions
from state_management import (
    create_context,
    device,
    device_action,
    device_parser,
    identifier,
)


@device
@dataclass
class Potentiometer:
    input_device: adc_actions.ADCAnalogInputDevice = identifier(
        analog_pin_actions.ctx
    )
    # constants used for mapping data to degree can be changed from the config including the cached_data
    max_degree: int = 285
    min_degree: int = 0
    max_data: int = 4096
    min_data: int = 0
    cached_data: int = None


ctx = create_context("potentiometer", Potentiometer)


@device_parser(ctx)
def parse_potentiometer(config: dict):
    """
    Parse a new potentiometer.

    Config:
    {
        input_device: ADCAnalogInputDevice = analog input device object
        max_degree: int = max degree of the potentiometer
        min_degree: int = min degree of the potentiometer
        max_data: int = max data of the potentiometer
        min_data: int = min data of the potentiometer
    } | str = analog input device object
    """
    if isinstance(config, str):
        config = {"input_device": config}
    print(config)
    pot = Potentiometer(**config)
    pot.cached_data = (
        pot.cached_data if pot.cached_data is not None else create_cached_data(pot)
    )
    return pot


@device_action(ctx)
def get_data(potentiometer: Potentiometer):
    """analog input device's bytearr to data

    Args:
        potentiometer (adc_actions.ADCAnalogInputDevice): potentiometer device object

    Returns:
        int: integer representation of the bytearr returned by the adc(adc_actions.ADCAnalogInputDevice)
    """
    return analog_pin_actions.read_data(potentiometer.input_device)


@device_action(ctx)
def get_degree(potentiometer: Potentiometer):
    """
    Get the degree of the potentiometer. Map function for converting data to degree.
    formula used: ((data - MIN_DATA) * ((MAX_DEGREE - MIN_DEGREE) / (MAX_DATA - MIN_DATA))) + MIN_DEGREE

    Args:
    potentiometer: Potentiometer = potentiometer object

    Returns:
    degree: int = degree of the potentiometer
    """
    min_data, min_degree, cached_data = (
        potentiometer.min_data,
        potentiometer.min_degree,
        potentiometer.cached_data,
    )
    data = get_data(potentiometer)
    return (data - min_data) * cached_data + min_degree


def create_cached_data(pot: Potentiometer) -> float:
    """(MAX_DEGREE - MIN_DEGREE) / (MAX_DATA - MIN_DATA)"""
    return (pot.max_degree - pot.min_degree) / (pot.max_data - pot.min_data)
