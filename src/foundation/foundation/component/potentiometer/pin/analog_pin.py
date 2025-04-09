from state_management._device import create_masked_context, device_action
from state_management.generic_devices.generic_devices import (
    AnalogInputDevice,
    analog_input_device_ctx,
)

ctx = create_masked_context(analog_input_device_ctx, "analog_pin")

@device_action(ctx)
def read_data(pin: AnalogInputDevice):
    return pin.value