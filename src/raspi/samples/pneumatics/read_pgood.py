from time import sleep

from component.muscle import pressure_actions
from state_management import configure_device

configure_device("src/raspi/pinconfig.json")

sleep(1)

while True:
    res = pressure_actions.is_pressure_ok("left_pressure")
    print(f"Pgood: {res}")
