import logging
from gpiozero import DigitalOutputDevice
from state_management import create_masked_context, device_action, output_device_ctx

ctx = create_masked_context(output_device_ctx, "valve")


@device_action(ctx)
def turn_valve_on(valve: DigitalOutputDevice) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    logging.info("turning valve on %s", valve)
    valve.on()


@device_action(ctx)
def turn_valve_off(valve: DigitalOutputDevice) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    logging.info("turning valve on %s", valve)
    valve.off()


@device_action(ctx)
def turn_valve(valve: DigitalOutputDevice, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_valve_on(valve) if state else turn_valve_off(valve)


@device_action(ctx)
def toggle_valve(valve: DigitalOutputDevice) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_valve(valve, not get_valve_state(valve))


@device_action(ctx)
def get_valve_state(valve: DigitalOutputDevice) -> bool:
    """
    Get the state of a valve.

    Args:
        valve: the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return valve.value == 1
