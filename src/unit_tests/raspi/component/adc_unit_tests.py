import unittest
from ....raspi.component.adc import ADC_action

class adc_unit_tests(unittest.TestCase):

    def test_ADCAnalogInputDevice_constructor(self):
        test_adc = ADC_action.ADC()
        test_address = 1
        test_adc_analog = ADC_action.ADCAnalogInputDevice(test_adc, test_address)
        self.assertEqual(test_adc_analog.adc, test_adc)
        self.assertEqual(test_adc_analog.address, test_address)

if __name__ == '__main__':
    unittest.main()