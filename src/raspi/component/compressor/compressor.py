from gpiozero import DigitalOutputDevice
from state_management import create_masked_context, device_action, output_device_ctx

compressor_ctx = create_masked_context(output_device_ctx, "compressor")
__all__ = [
    "compressor_attr",
    "turn_compressor_on",
    "turn_compressor_off",
    "turn_valve",
    "toggle_compressor",
    "get_compressor_state",
]


@device_action(compressor_ctx)
def turn_compressor_on(valve: DigitalOutputDevice) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    valve.on()


@device_action(compressor_ctx)
def turn_compressor_off(compressor: DigitalOutputDevice) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    compressor.off()


@device_action(compressor_ctx)
def turn_valve(compressor: DigitalOutputDevice, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_compressor_on(compressor) if state else turn_compressor_off(compressor)


@device_action(compressor_ctx)
def toggle_valve(compressor: DigitalOutputDevice) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_valve(compressor, not get_valve_state(compressor))


@device_action(compressor_ctx)
def get_valve_state(compressor: DigitalOutputDevice) -> bool:
    """
    Get the state of a valve.

    Args:
        valve (DigitalOutputDevice): the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return compressor.value
