from dataclasses import dataclass, field
from time import sleep

from gpiozero import DigitalOutputDevice
from state_management import (
    create_generic_context,
    device,
    device_parser,
    identifier,
    output_device_ctx,
    register_device,
)
from state_management.utils.deviceMock import value_change

from .pin import latch_pin_actions

USE = False
ENABLE_DURATION = 0.1


# helper method to convert an integer to a bitfield
# used for converting address of the devices hooked on the latch to a bitfield
# returns a list of 1s and 0s
def bitfield(n, length=3):
    res = [1 if digit == "1" else 0 for digit in bin(n)[2:]]
    return [0] * (length - len(res)) + res


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
        # this might need to change in the future as it might need to be check if the latch has actually switched state
        self._value = value

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


@device
@dataclass
class Latch:
    pins: dict[str, int]
    queue: list[tuple[str, int]] = field(default_factory=list)
    lock: bool = False
    data: DigitalOutputDevice = identifier(latch_pin_actions.data_pin_ctx)
    enab: DigitalOutputDevice = identifier(latch_pin_actions.enab_pin_ctx)
    addr_1: DigitalOutputDevice = identifier(latch_pin_actions.addr_pin_ctx)
    addr_2: DigitalOutputDevice = identifier(latch_pin_actions.addr_pin_ctx)
    addr_3: DigitalOutputDevice = identifier(latch_pin_actions.addr_pin_ctx)
    _identifier: str = field(default="latch")

    def set(self, addr: str, state: int) -> None:
        self.queue.append((addr, state))
        if not self.lock:
            self.process_queue()

    def process_queue(self):
        self.lock = True
        while len(self.queue) > 0:
            addr, newState = self.queue.pop(0)
            self._set_one_device(addr, newState)
            # not using asyncio.sleep because real output devices are not async
        self.lock = False

    def _set_one_device(self, addr, newState):
        b0, b1, b2 = bitfield(addr)
        latch_pin_actions.set_addr(self.addr_1, b0)
        latch_pin_actions.set_addr(self.addr_2, b1)
        latch_pin_actions.set_addr(self.addr_3, b2)
        latch_pin_actions.set_data(self.data, newState)
        latch_pin_actions.set_enab(self.enab, 0)
        sleep(ENABLE_DURATION)
        latch_pin_actions.set_enab(self.enab, 1)


ctx = create_generic_context("latch", [Latch])


@device_parser(ctx)
def parse_latch(data: dict) -> Latch:
    """
    Parse a latch from a dictionary.

    Args:
        data (dict): the dictionary to parse

    Returns:
        (Latch) the parsed latch
    """
    latch = Latch(**data)

    if output_device_ctx is None:
        raise ValueError(
            "No output device parser found. Makesure to define output device before the latch"
        )
    if not VirtualDigitalOutputDevice in output_device_ctx.allowed_classes:
        output_device_ctx.allowed_classes = (
            VirtualDigitalOutputDevice,
            *output_device_ctx.allowed_classes,
        )
    for identifier, addr in latch.pins.items():
        dev_identifier = f"{latch._identifier}.{identifier}"
        virtualDevice = VirtualDigitalOutputDevice(latch, addr)
        register_device(output_device_ctx, dev_identifier, virtualDevice)

    return latch
