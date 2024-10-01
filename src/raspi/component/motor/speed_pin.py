from gpiozero import DigitalOutputDevice

from raspi.state_management import create_output_device_component

(speed_pin_action, speed_pin_attr) = create_output_device_component("speedPin")
__all__ = [
    "register_speedPin",
    "speed_pin_attr",
    "set",
]


@speed_pin_action
def set(speedPin: DigitalOutputDevice, speed: int) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    speedPin.value = speed