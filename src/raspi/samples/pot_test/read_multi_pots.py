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
