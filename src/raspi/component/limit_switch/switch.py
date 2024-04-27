from gpiozero import DigitalInputDevice
from state_management.device import create_masked_context, device_action
from state_management.generic_devices.generic_devices import input_device_ctx

limit_ctx = create_masked_context(input_device_ctx, "limit_interrupt")


@device_action(limit_ctx)
def is_limit_switch_active(device: DigitalInputDevice) -> bool:
    """
    Check if any limit switch connected to the device is currently enabled.

    [TODO: write the rest of these docs]
    """
    return device.is_active


@device_action(limit_ctx)
def on_limit_switch_activated(device: DigitalInputDevice, action: callable) -> None:
    device.when_activated = action


@device_action(limit_ctx)
def on_limit_switch_deactivated(device: DigitalInputDevice, action: callable) -> None:
    device.when_deactivated = action
