# This script reads the degrees of all 8 potentiometers and prints them to the console.
# Author: Hiroto Takeuchi @hiromon0125
# Date: 2024-04-13
# PR: #26 (https://github.com/RIT-MDRC/Catbot/pull/26)

from time import sleep

from component.potentiometer import potentiometer_actions
from state_management import configure_device

configure_device("src/raspi/pinconfig.json")

sleep(2)
while True:
    for n in range(8):
        print(
            "{0:.3f}".format(potentiometer_actions.get_degree(f"pot{n+1}")).zfill(8),
            end=" ",
        )
    print("")
