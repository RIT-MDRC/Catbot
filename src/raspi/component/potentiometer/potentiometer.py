from component.adc import ADC_action
from state_management.device import create_masked_context, device_action

ctx = create_masked_context(ADC_action.analog_input_device_ctx, "potentiometer")


@device_action(ctx)
def get_degree(potentiometer: ADC_action.ADCAnalogInputDevice):
    return potentiometer.value
