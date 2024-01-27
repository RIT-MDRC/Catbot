from .util import compressor_action


@compressor_action
def turn_compressor_on(valve) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    valve.on()


@compressor_action
def turn_compressor_off(compressor) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    compressor.off()


@compressor_action
def turn_value(compressor, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_compressor_on(compressor) if state else turn_compressor_off(compressor)


@compressor_action
def toggle_valve(compressor) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_value(compressor, not get_valve_state(compressor))


@compressor_action
def get_valve_state(compressor) -> bool:
    """
    Get the state of a valve.

    Args:
        valve (DigitalOutputDevice): the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return compressor.value
