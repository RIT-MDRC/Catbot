from asyncio import sleep
from dataclasses import dataclass, field
from multiprocessing import Process

from gpiozero import DigitalOutputDevice
from state_management.device import DEVICE_PARSERS, create_device_store
from state_management.utils.deviceMock import value_change

from . import latch_pin_actions

ENABLE_DURATION = 0.1


# helper method to convert an integer to a bitfield
# returns a list of 1s and 0s
def bitfield(n):
    return [1 if digit == "1" else 0 for digit in bin(n)[2:]]


class VirtualDigitalOutputDevice:
    _value: int

    def __init__(self, latch, addr):
        self.latch = latch
        self.addr = addr
        self._value = 0
        self.pin = addr  # debugging purposes

    @value_change
    def on(self):
        self._value = 1

    @value_change
    def off(self):
        self._value = 0

    @value_change
    def toggle(self):
        new_val = 1 - self._value
        self._value = new_val

    def set_value(self, value):
        self.latch.set(self.addr, value)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value: int):
        if value not in [0, 1]:
            raise ValueError("Value must be 0 or 1")
        self.set_value(value)

    def __repr__(self) -> str:
        return f"VirtualDigitalOutputDevice(pin={self.pin}, value={self._value})"


@latch_pin_actions.data_pin_attr("data")
@latch_pin_actions.enab_pin_attr("enab")
@latch_pin_actions.addr_pin_attr(("addr_1", "addr_2", "addr_3"))
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
    _identifier: str = field(default="latch")

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

    def set(self, addr: str, state: int) -> None:
        self.queue.append((addr, state))
        if self.lock:
            return
        # Process the queue in a separate core to avoid blocking the main thread
        Process(target=self.process_queue).start()

    def process_queue(self):
        self.lock = True
        while len(self.queue) > 0:
            latch_pin_actions.set_enab(self.enab, 1)
            addr, newState = self.queue.pop(0)
            b0, b1, b2 = bitfield(addr)
            latch_pin_actions.set_addr(self.addr_1, b0)
            latch_pin_actions.set_addr(self.addr_2, b1)
            latch_pin_actions.set_addr(self.addr_3, b2)
            latch_pin_actions.set_data(self.data, newState)
            latch_pin_actions.set_enab(self.enab, 0)
            sleep(ENABLE_DURATION)
        latch_pin_actions.set_enab(self.enab, 0)
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
