from gpiozero import DigitalInputDevice
from state_management import create_masked_context, device_action
from state_management.generic_devices.generic_devices import input_device_ctx

ctx = create_masked_context(input_device_ctx, "expander_interrupt")


@device_action(ctx)
def on_expander_activated(device: DigitalInputDevice, action: callable) -> bool:
    device.when_activated = action
    return True


@device_action(ctx)
def on_expander_deactivated(device: DigitalInputDevice, action: callable) -> bool:
    device.when_deactivated = action
    return True
