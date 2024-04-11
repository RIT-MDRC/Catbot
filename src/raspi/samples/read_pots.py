import asyncio
from time import sleep

from component.potentiometer import potentiometer_actions
from state_management import configure_device

configure_device("src/raspi/pinconfig.json")


while True:
    print("Reading potentiometer_1")
    print(potentiometer_actions.get_degree("pot1"))
    sleep(1)
