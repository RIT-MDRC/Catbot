from gpiozero import PWMOutputDevice
from state_management import create_pwm_output_device_component

(speed_pin_action, speed_pin_attr) = create_pwm_output_device_component("speedPin")
__all__ = [
    "register_speedPin",
    "speed_pin_attr",
    "set",
]


@speed_pin_action
def get(speedPin: PWMOutputDevice) -> float:
    """
    Get the current PWM output

    Args:
        speedPin (PWMOutputDevice): the device to get the speed of
    """
    return speedPin.value


@speed_pin_action
def set(speedPin: PWMOutputDevice, speed: int) -> float:
    """
    Set the PWM outout to be the absolute number of the speed value

    Args:
        speedPin (PWMOutputDevice): the device to set the speed of
        speed (int): the speed value to set. The code will take an absolute value of the speed
    """
    speedPin.value = abs(speed)
    return get(speedPin)


@speed_pin_action
def stop(speedPin: PWMOutputDevice) -> float:
    """
    Stop the PWM output

    Args:
        speedPin (PWMOutputDevice): the device to stop sending PWM output
    """
    speedPin.off()
    return get(speedPin)
