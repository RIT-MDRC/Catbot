import logging

from gpiozero import DigitalOutputDevice
from state_management import create_masked_context, device_action, output_device_ctx

ctx = create_masked_context(output_device_ctx, "stepPin")


@device_action(ctx)
def set_high(stepPin: DigitalOutputDevice) -> None:
    """
    Set the step pin to high

    Args:
        stepPin (DigitalOutputDevice): the step pin to set to high
    """
    stepPin.on()


@device_action(ctx)
def set_low(stepPin: DigitalOutputDevice) -> None:
    """
    Set the step pin to low

    Args:
        stepPin (DigitalOutputDevice): the step pin to set to low
    """
    stepPin.off()


@device_action(ctx)
def toggle(stepPin: DigitalOutputDevice) -> None:
    """
    Toggle the step pin

    Args:
        stepPin (DigitalOutputDevice): the step pin to toggle
    """
    stepPin.toggle()


@device_action(ctx)
def check_high(stepPin: DigitalOutputDevice) -> bool:
    """
    Check if the step pin is high

    Args:
        stepPin (DigitalOutputDevice): the step pin to check
    """
    return stepPin.is_active


@device_action(ctx)
def check_low(stepPin: DigitalOutputDevice) -> bool:
    """
    Check if the step pin is low

    Args:
        stepPin (DigitalOutputDevice): the step pin to check
    """
    return not stepPin.is_active


@device_action(ctx)
def check_state(stepPin: DigitalOutputDevice) -> bool:
    """
    Check the state of the step pin

    Args:
        stepPin (DigitalOutputDevice): the step pin to check
    """
    return stepPin.value
