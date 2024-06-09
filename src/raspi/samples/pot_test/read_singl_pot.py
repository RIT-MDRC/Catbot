# This script reads the raw bytearray and calculated degree of potentiometer n and prints them to the console.
# change the value of n to read the desired potentiometer.
# Author: Hiroto Takeuchi @hiromon0125
# Date: 2024-04-13
# PR: #26 (https://github.com/RIT-MDRC/Catbot/pull/26)

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
