from time import sleep

from component.potentiometer import potentiometer_actions
from state_management import configure_device

# pot number to read
n = 4

configure_device("src/raspi/pinconfig.json")
sleep(2)

while True:
    print(potentiometer_actions.get_degree(f"pot{n}")[1])
