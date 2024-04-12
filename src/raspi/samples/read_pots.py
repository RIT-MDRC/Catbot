import asyncio
from time import sleep

from component.potentiometer import potentiometer_actions
from state_management import configure_device

configure_device("src/raspi/pinconfig.json")

sleep(2)
while True:
    for n in range(8):
        print(f"Reading pot{n+1}")
        try:
            print(potentiometer_actions.get_degree(f"pot{n+1}"))
        except Exception as e:
            print(f"failed{n+1}: {e}")
        sleep(1)
