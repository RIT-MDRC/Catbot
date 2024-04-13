from component.adc import ADC_action
from state_management.device import create_masked_context, device_action
from smbus2 import i2c_msg

ctx = create_masked_context(ADC_action.analog_input_device_ctx, "potentiometer")

class Potentiometer:
    MAX_ANG = 285
    MIN_ANG = 0

    current_degrees: int

    def read_data(self):
        write = i2c_msg.write(self.address, [register])
        read = i2c_msg.read(self.address, 2)
        return
    
    def convert_to_degrees(self, register):
    # assuming we are taking in a 12-bit-string
    
        if register > self.MAX_ANG:
            return "Error" # Shouldn't do this but Im lazy rn
            # Ask Hiro if he wants number over 285 to loop back around or to error

        return





@device_action(ctx)
def get_degree(potentiometer: ADC_action.ADCAnalogInputDevice):
    return potentiometer.value

