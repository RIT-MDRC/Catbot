from time import sleep

from component.io_expander import io_expander_actions
from state_management import configure_device

def trigger():
    print("a limit switch state change has occurred")
    # ioe = io_expander_actions.parse_io_expander("io_expander_1")
    # ioe.mcp.clear_ints()

configure_device("src/raspi/pinconfig.json")

io_expander_actions.on_limit_switch_state_change("interrupt_a1", trigger)

while True:
    ...