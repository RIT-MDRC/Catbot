from gpiozero import DigitalOutputDevice

from ..util.device import create_output_device_component

(compressor_action, register_compressor) = create_output_device_component("compressor")
__all__ = [
    "register_compressor",
    "turn_compressor_on",
    "turn_compressor_off",
    "turn_valve",
    "toggle_compressor",
    "get_compressor_state",
]


@compressor_action
def turn_compressor_on(valve: DigitalOutputDevice) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    valve.on()


@compressor_action
def turn_compressor_off(compressor: DigitalOutputDevice) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    compressor.off()


@compressor_action
def turn_valve(compressor: DigitalOutputDevice, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_compressor_on(compressor) if state else turn_compressor_off(compressor)


@compressor_action
def toggle_valve(compressor: DigitalOutputDevice) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_valve(compressor, not get_valve_state(compressor))


@compressor_action
def get_valve_state(compressor: DigitalOutputDevice) -> bool:
    """
    Get the state of a valve.

    Args:
        valve (DigitalOutputDevice): the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return compressor.value
