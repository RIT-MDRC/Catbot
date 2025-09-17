from state_management import (
    AnalogInputDevice,
    analog_input_device_ctx,
    create_masked_context,
    device_action,
)

ctx = create_masked_context(analog_input_device_ctx, "pressure")


@device_action(ctx)
def get_pressure(device: AnalogInputDevice) -> int:
    """
    Return the pressure's readings.

    Args:
        name (str): the name of the pressure sensor

    Returns:
        (int) the pressure from the pressure sensor
    """
    return device.value


@device_action(ctx)
def gt(device: AnalogInputDevice, value: int = 0.5) -> bool:
    """
    Check if the pressure is greater than a value.

    Args:
        name (str): the name of the pressure sensor
        value (int): the value to check against (default: 0.5)

    Returns:
        (bool) true if the condition is met, false otherwise
    """
    return device.value > value


@device_action(ctx)
def lt(device: AnalogInputDevice, value: int = 0.5) -> bool:
    """
    Check if the pressure is less than a value.

    Args:
        name (str): the name of the pressure sensor
        value (int): the value to check against (default: 0.5)

    Returns:
        (bool) true if the condition is met, false otherwise
    """
    return device.value < value
