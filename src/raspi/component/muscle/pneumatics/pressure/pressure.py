from gpiozero import DigitalInputDevice
from state_management import create_masked_context, device_action, input_device_ctx

ctx = create_masked_context(input_device_ctx, "pressure")


@device_action(ctx)
def is_pressure_ok(device: DigitalInputDevice) -> bool:
    """
    Check if the pressure sensor is ok.

    Args:
        name (str): the name of the pressure sensor

    Returns:
        (bool) true if the pressure sensor is ok, false otherwise
    """
    return device.is_active


@device_action(ctx)
def on_pressure_active(device: DigitalInputDevice, action: callable) -> None:
    """
    Add a new pressure sensor change event.

    Args:
        name (str): the name of the pressure sensor
        action (callable): the action to perform when the pressure sensor changes
    """
    device.when_activated = action


@device_action(ctx)
def on_pressure_deactive(device: DigitalInputDevice, action: callable) -> None:
    """
    Add a new pressure sensor change event.

    Args:
        name (str): the name of the pressure sensor
        action (callable): the action to perform when the pressure sensor changes
    """
    device.when_deactivated = action
