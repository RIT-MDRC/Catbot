from time import sleep

from component.potentiometer import potentiometer_actions
from state_management import configure_device

# pot number to read
n = 5

configure_device("src/raspi/pinconfig.json")
sleep(2)

while True:
    raw = potentiometer_actions.ADC_action.get_data(f"adc_1.pot{n}")
    data = "{0:.4f}".format(potentiometer_actions.get_degree(f"pot{n}")).zfill(8)
    print(f"{data}deg bytearray:{raw}")
