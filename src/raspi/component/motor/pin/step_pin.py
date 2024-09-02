from gpiozero import DigitalOutputDevice
from state_management import create_masked_context, device_action, output_device_ctx

step_ctx = create_masked_context(output_device_ctx, "stepPin")
direction_ctx = create_masked_context(output_device_ctx, "directionPin")


@device_action(step_ctx)
def set_high(stepPin: DigitalOutputDevice) -> None:
    """
    Set the step pin to high

    Args:
        stepPin (DigitalOutputDevice): the step pin to set to high
    """
    stepPin.on()


@device_action(step_ctx)
def set_low(stepPin: DigitalOutputDevice) -> None:
    """
    Set the step pin to low

    Args:
        stepPin (DigitalOutputDevice): the step pin to set to low
    """
    stepPin.off()


@device_action(step_ctx)
def toggle(stepPin: DigitalOutputDevice) -> None:
    """
    Toggle the step pin

    Args:
        stepPin (DigitalOutputDevice): the step pin to toggle
    """
    stepPin.toggle()


@device_action(step_ctx)
def check_direction_high(stepPin: DigitalOutputDevice) -> bool:
    """
    Check if the step pin is high

    Args:
        stepPin (DigitalOutputDevice): the step pin to check
    """
    return stepPin.is_active


@device_action(step_ctx)
def check_direction_low(stepPin: DigitalOutputDevice) -> bool:
    """
    Check if the step pin is low

    Args:
        stepPin (DigitalOutputDevice): the step pin to check
    """
    return not stepPin.is_active


@device_action(step_ctx)
def check_direction_state(stepPin: DigitalOutputDevice) -> bool:
    """
    Check the state of the step pin

    Args:
        stepPin (DigitalOutputDevice): the step pin to check
    """
    return stepPin.value


@device_action(direction_ctx)
def set_direction_high(directionPin: DigitalOutputDevice) -> None:
    """
    Set the direction pin to low

    Args:
        directionPin (DigitalOutputDevice): the direction pin to set to low
    """
    directionPin.on()


@device_action(direction_ctx)
def set_direction_low(directionPin: DigitalOutputDevice) -> None:
    """
    Set the direction pin to low

    Args:
        directionPin (DigitalOutputDevice): the direction pin to set to low
    """
    directionPin.off()


@device_action(direction_ctx)
def toggle_direction(directionPin: DigitalOutputDevice) -> None:
    """
    Toggle the direction pin

    Args:
        directionPin (DigitalOutputDevice): the direction pin to toggle
    """
    directionPin.toggle()


@device_action(direction_ctx)
def set_direction(directionPin: DigitalOutputDevice, direction: int) -> None:
    """
    Set the direction of the direction pin

    Args:
        directionPin (DigitalOutputDevice): the direction pin to set
        direction (bool): the direction to set
    """
    directionPin.value = direction


@device_action(direction_ctx)
def check_direction_high(directionPin: DigitalOutputDevice) -> bool:
    """
    Check if the direction pin is high

    Args:
        directionPin (DigitalOutputDevice): the direction pin to check
    """
    return directionPin.is_active


@device_action(direction_ctx)
def check_direction_low(directionPin: DigitalOutputDevice) -> bool:
    """
    Check if the direction pin is low

    Args:
        directionPin (DigitalOutputDevice): the direction pin to check
    """
    return not directionPin.is_active
