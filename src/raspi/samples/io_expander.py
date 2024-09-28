import logging
from signal import pause
from time import sleep

from component.io_expander import io_expander_actions
from component.limit_switch import limit_switch_actions
from state_management import configure_device

io_expander_actions.USE = True


configure_device("src/raspi/pinconfig.json")


def print_activated():
    logging.info("Limit switch activated")


def print_deactivated():
    logging.info("Limit switch deactivated")


for n in range(1, 9):
    limit_switch_actions.on_limit_switch_activated(
        f"io_expander_1.channel_{n}", print_activated
    )
    limit_switch_actions.on_limit_switch_deactivated(
        f"io_expander_1.channel_{n}", print_deactivated
    )

while True:
    sleep(1)
    logging.info("Main loop running")
