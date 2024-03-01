from gpiozero import DigitalOutputDevice
from state_management.generic_devices import create_output_device_component

addr_pin_action, addr_pin_attr = create_output_device_component("addr_pin")
data_pin_action, data_pin_attr = create_output_device_component("data_pin")
enab_pin_action, enab_pin_attr = create_output_device_component("enab_pin")

__all__ = [
    "addr_pin_attr",
    "data_pin_attr",
    "enab_pin_attr",
    "set_addr",
    "set_data",
    "set_enab",
]


@addr_pin_action
def set_addr(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state / state else dev.off()


@data_pin_action
def set_data(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the data pin.

    Args:
        dev (DigitalOutputDevice): the data pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state / state else dev.off()


@enab_pin_action
def set_enab(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the enable pin.

    Args:
        dev (DigitalOutputDevice): the enable pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state / state else dev.off()
