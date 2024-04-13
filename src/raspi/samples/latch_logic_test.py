from component.latch.pin import latch_pin_actions
from state_management.device import configure_device

ENAB = "lat_enab"
DATA = "lat_data"
ADDR1 = "lat_addr_1"
ADDR2 = "lat_addr_2"
ADDR3 = "lat_addr_3"


def print_latch_state():
    print(
        f"E: {latch_pin_actions.get_enab(ENAB)} D: {latch_pin_actions.get_data(DATA)} ADDR: {latch_pin_actions.get_addr(ADDR1)}{latch_pin_actions.get_addr(ADDR2)}{latch_pin_actions.get_addr(ADDR3)}"
    )


configure_device("src/raspi/pinconfig.json")
print_latch_state()
while True:
    i = input("Enter a pin(d,e,1,2,3): ")
    match i:
        case "d":
            print("You entered d")
            latch_pin_actions.toggle_data(DATA)
        case "e":
            print("You entered e")
            latch_pin_actions.toggle_enab(ENAB)
        case "1":
            print("You entered 1")
            latch_pin_actions.toggle_addr(ADDR1)
        case "2":
            print("You entered 2")
            latch_pin_actions.toggle_addr(ADDR2)
        case "3":
            print("You entered 3")
            latch_pin_actions.toggle_addr(ADDR3)
        case _:
            print("Invalid input")
    print_latch_state()
