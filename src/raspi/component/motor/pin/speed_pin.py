import logging
from gpiozero import PWMOutputDevice
from state_management import create_masked_context, device_action, pwm_output_device_ctx

ctx = create_masked_context(pwm_output_device_ctx, "speedPin")


@device_action(ctx)
def get(speedPin: PWMOutputDevice) -> float:
    """
    Get the current PWM output

    Args:
        speedPin (PWMOutputDevice): the device to get the speed of
    """
    return speedPin.value


@device_action(ctx)
def set(speedPin: PWMOutputDevice, speed: int) -> float:
    """
    Set the PWM outout to be the absolute number of the speed value

    Args:
        speedPin (PWMOutputDevice): the device to set the speed of
        speed (int): the speed value to set. The code will take an absolute value of the speed
    """
    logging.info("Setting speed device to %s", speed)
    speedPin.value = abs(speed)
    return get(speedPin)


@device_action(ctx)
def stop(speedPin: PWMOutputDevice) -> float:
    """
    Stop the PWM output

    Args:
        speedPin (PWMOutputDevice): the device to stop sending PWM output
    """
    speedPin.off()
    return get(speedPin)


@device_action(ctx)
def check_speed(speedPin: PWMOutputDevice, speed: float) -> bool:
    return speedPin.value == speed
