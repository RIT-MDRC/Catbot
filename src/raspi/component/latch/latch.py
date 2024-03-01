from asyncio import sleep
from dataclasses import dataclass, field
from multiprocessing import Process

from gpiozero import DigitalOutputDevice
from state_management.device import DEVICE_PARSERS, create_device_store
from state_management.utils.deviceMock import value_change

from .pin import addr_pin_attr, data_pin_attr, enab_pin_attr, set_data, set_enab

ENABLE_DURATION = 0.1


# helper method to convert an integer to a bitfield
# returns a list of 1s and 0s
def bitfield(n):
    return [1 if digit == "1" else 0 for digit in bin(n)[2:]]


class VirtualDigitalOutputDevice:
    value: int

    def __init__(self, latch, addr):
        self.latch = latch
        self.addr = addr
        self.value = 0

    @value_change
    def on(self):
        self.set_value(1)

    @value_change
    def off(self):
        self.set_value(0)

    @value_change
    def toggle(self):
        new_val = 1 - self.value
        self.set_value(new_val)

    def set_value(self, value):
        self.latch.set(self.addr, value)
        self.value = value


@data_pin_attr("data")
@enab_pin_attr("enab")
@addr_pin_attr(("addr_1", "addr_2", "addr_3"))
@dataclass
class Latch:
    data: DigitalOutputDevice
    enab: DigitalOutputDevice
    addr_1: DigitalOutputDevice
    addr_2: DigitalOutputDevice
    addr_3: DigitalOutputDevice
    pins: dict[str, int]
    queue: list[tuple[str, int]] = field(default_factory=list)
    lock: bool = False
    _identifier: str

    def __post_init__(self):
        output_device_parser = DEVICE_PARSERS.get("output_device", None)
        if output_device_parser is None:
            raise ValueError(
                "No output device parser found. Makesure to define output device before the latch"
            )
        for identifier, addr in self.pins.items():
            dev_identifier = f"{self._identifier}.{identifier}"
            virtualDevice = VirtualDigitalOutputDevice(self, addr)
            if dev_identifier in output_device_parser.store:
                raise ValueError(f"Device {dev_identifier} already exists")
            output_device_parser.store[dev_identifier] = virtualDevice

    @value_change
    def set(self, addr: str, state: int) -> None:
        self.queue.append((addr, state))
        if self.lock:
            return
        # Process the queue in a separate core to avoid blocking the main thread
        Process(target=self.process_queue).start()

    def process_queue(self):
        self.lock = True
        while len(self.queue) > 0:
            set_enab(self.enab, 1)
            addr, newState = self.queue.pop(0)
            bits = bitfield(addr)
            set_addr(self.addr_1, bits[0])
            set_addr(self.addr_2, bits[1])
            set_addr(self.addr_3, bits[2])
            set_data(self.data, newState)
            set_enab(self.enab, 0)
            sleep(ENABLE_DURATION)
        set_enab(self.enab, 0)
        self.lock = False


latch_action, latch_parser, latch_attr = create_device_store("latch", [Latch])


@latch_parser
def parse_latch(data: dict) -> Latch:
    """
    Parse a latch from a dictionary.

    Args:
        data (dict): the dictionary to parse

    Returns:
        (Latch) the parsed latch
    """
    return Latch(**data)


@latch_action
def set_addr(dev: DigitalOutputDevice, state: int) -> None:
    """
    Set the address pin.

    Args:
        dev (DigitalOutputDevice): the address pin
        state (int): 1 to turn the pin on, 0 to turn it off
    """
    dev.on() if state / state else dev.off()
