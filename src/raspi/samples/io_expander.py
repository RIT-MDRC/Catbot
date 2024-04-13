# from time import sleep

# from component.io_expander import io_expander_actions
# from state_management import configure_device

# def limit_hit():
#     print("limit switch hit")

# configure_device("src/raspi/pinconfig.json")

# io_expander_actions.on_limit_switch_activate("interrupt_a1", limit_hit)

# while True:
#     sleep(0.01)

from time import sleep

from gpiozero import DigitalInputDevice

def limit_hit():
    print("limit switch hit")

interrupt_pin = DigitalInputDevice(8)
interrupt_pin.when_activated = limit_hit

print("configured interrupt pin")

while True:
    sleep(0.01)