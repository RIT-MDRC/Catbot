from gpiozero import DigitalOutputDevice
from state_management import create_masked_context, device_action, output_device_ctx

enab_pin_ctx = create_masked_context(output_device_ctx, "enab_pin")
data_pin_ctx = create_masked_context(output_device_ctx, "data_pin")
addr_pin_ctx = create_masked_context(output_device_ctx, "addr_pin")

__all__ = [
    "enab_pin_ctx",
    "data_pin_ctx",
    "addr_pin_ctx",
    "set_addr",
    "set_data",
    "set_enab",
]


@device_action(addr_pin_ctx)
def set_addr(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state > 0 else dev.off()


@device_action(data_pin_ctx)
def set_data(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the data pin.

    Args:
        dev (DigitalOutputDevice): the data pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state > 0 else dev.off()


@device_action(enab_pin_ctx)
def set_enab(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the enable pin.

    Args:
        dev (DigitalOutputDevice): the enable pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state > 0 else dev.off()
