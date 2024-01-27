from .util import valve_action


@valve_action
def turn_valve_on(valve) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    valve.on()


@valve_action
def turn_valve_off(valve) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    valve.off()


@valve_action
def turn_valve(valve, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_valve_on(valve) if state else turn_valve_off(valve)


@valve_action
def toggle_valve(valve) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_valve(valve, not get_valve_state(valve))


@valve_action
def get_valve_state(valve) -> bool:
    """
    Get the state of a valve.

    Args:
        valve: the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return valve.value == 1
