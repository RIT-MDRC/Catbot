import logging
from time import sleep

from component.muscle import muscle_actions
from state_management.device import configure_device

configure_device("src/raspi/pinconfig.json")

sleep(1)

while True:
    logging.info("flexing muscle(valve on)")
    muscle_actions.contract("left_muscle")
    sleep(1)
    logging.info("relaxing muscle(valve off)")
    muscle_actions.relax("left_muscle")
    sleep(1)
