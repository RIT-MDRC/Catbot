from gpiozero import DigitalOutputDevice

from ...util.generic_devices import create_input_device_component

(pressure_action, *_) = create_input_device_component("pressure")
__all__ = [
    "register_pressure",
    "is_pressure_ok",
    "on_pressure_active",
    "on_pressure_deactive",
]


@pressure_action
def is_pressure_ok(device: DigitalOutputDevice) -> bool:
    """
    Check if the pressure sensor is ok.

    Args:
        name (str): the name of the pressure sensor

    Returns:
        (bool) true if the pressure sensor is ok, false otherwise
    """
    return device.is_active


@pressure_action
def on_pressure_active(device: DigitalOutputDevice, action: callable) -> None:
    """
    Add a new pressure sensor change event.

    Args:
        name (str): the name of the pressure sensor
        action (callable): the action to perform when the pressure sensor changes
    """
    device.when_activated = action


@pressure_action
def on_pressure_deactive(device: DigitalOutputDevice, action: callable) -> None:
    """
    Add a new pressure sensor change event.

    Args:
        name (str): the name of the pressure sensor
        action (callable): the action to perform when the pressure sensor changes
    """
    device.when_deactivated = action
