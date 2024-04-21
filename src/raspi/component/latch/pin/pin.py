import logging

from gpiozero import DigitalOutputDevice
from state_management import create_masked_context, device_action, output_device_ctx

enab_pin_ctx = create_masked_context(output_device_ctx, "enab_pin")
data_pin_ctx = create_masked_context(output_device_ctx, "data_pin")
addr_pin_ctx = create_masked_context(output_device_ctx, "addr_pin")


@device_action(addr_pin_ctx)
def set_addr(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state > 0 else dev.off()


@device_action(addr_pin_ctx)
def get_addr(dev: DigitalOutputDevice) -> int:
    """
    Get the state of the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin

    Returns:
        int: 1 if the pin is on, 0 if the pin is off
    """
    return dev.value


@device_action(addr_pin_ctx)
def toggle_addr(dev: DigitalOutputDevice) -> int:
    """
    Toggle the state of the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin

    Returns:
        int: 1 if the pin is on, 0 if the pin is off
    """
    return dev.toggle()


@device_action(data_pin_ctx)
def set_data(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the data pin.

    Args:
        dev (DigitalOutputDevice): the data pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    logging.debug("Setting data pin to %s", state)
    dev.on() if state > 0 else dev.off()


@device_action(data_pin_ctx)
def get_data(dev: DigitalOutputDevice) -> int:
    """
    Get the state of the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin

    Returns:
        int: 1 if the pin is on, 0 if the pin is off
    """
    logging.debug("Getting data pin value")
    return dev.value


@device_action(data_pin_ctx)
def toggle_data(dev: DigitalOutputDevice) -> int:
    """
    Toggle the state of the data pin.

    Args:
        dev (DigitalOutputDevice): the address pin

    Returns:
        int: 1 if the pin is on, 0 if the pin is off
    """
    logging.debug("Toggling data pin")
    return dev.toggle()


@device_action(enab_pin_ctx)
def set_enab(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the enable pin.

    Args:
        dev (DigitalOutputDevice): the enable pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state > 0 else dev.off()


@device_action(enab_pin_ctx)
def get_enab(dev: DigitalOutputDevice) -> int:
    """
    Get the state of the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin

    Returns:
        int: 1 if the pin is on, 0 if the pin is off
    """
    return dev.value


@device_action(enab_pin_ctx)
def toggle_enab(dev: DigitalOutputDevice) -> int:
    """
    Toggle the state of the enab pin.

    Args:
        dev (DigitalOutputDevice): the address pin

    Returns:
        int: 1 if the pin is on, 0 if the pin is off
    """
    return dev.toggle()
