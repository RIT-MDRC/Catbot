from gpiozero import DigitalOutputDevice

from raspi.state_management import create_output_device_component

valve_action = create_output_device_component("valve")
__all__ = [
    "register_valve",
    "turn_valve_on",
    "turn_valve_off",
    "turn_valve",
    "toggle_valve",
    "get_valve_state",
]


@valve_action
def turn_valve_on(valve: DigitalOutputDevice) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    valve.on()


@valve_action
def turn_valve_off(valve: DigitalOutputDevice) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    valve.off()


@valve_action
def turn_valve(valve: DigitalOutputDevice, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_valve_on(valve) if state else turn_valve_off(valve)


@valve_action
def toggle_valve(valve: DigitalOutputDevice) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_valve(valve, not get_valve_state(valve))


@valve_action
def get_valve_state(valve: DigitalOutputDevice) -> bool:
    """
    Get the state of a valve.

    Args:
        valve: the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return valve.value == 1
