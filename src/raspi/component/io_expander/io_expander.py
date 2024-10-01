import logging
from dataclasses import dataclass, field

import board
import busio
from state_management.utils import is_dev, FakeMCP23017, FakeDirection, FakePull
from gpiozero import DigitalInputDevice
from state_management import (
    create_context,
    device,
    device_parser,
    identifier,
    input_device_ctx,
    register_device,
)

from . import interrupt_pin_action

if not is_dev():
    from digitalio import Direction, Pull
    from adafruit_mcp230xx.mcp23017 import MCP23017, DigitalInOut

# Plugin for IOExpander. Set this to True in the sample script file if you use a component that uses the IOExpander
USE = False


@dataclass
class IOExpanderInputDevice:
    pin: DigitalInOut
    pin_num: int
    name: str

    when_activated: callable = None
    when_deactivated: callable = None

    @property
    def value(self):
        """Get the value of the pin
        ```py
        pin = IOExpanderInputDevice()
        if pin.value:
            # do something
        ```
        """
        return self.pin.value

    @property
    def is_active(self):
        """Check if the pin is active"""
        return self.pin.value


if not IOExpanderInputDevice in input_device_ctx.allowed_classes:
    input_device_ctx.allowed_classes += (IOExpanderInputDevice,)


@device
@dataclass
class IOExpander:
    """
    16-bit I/O expander, currently only supports input devices.

    config schema:
    {
        address: str = i2c address of the device i.e. "0x20",
        interrupt_pin: DigitalInputDevice = identifier(input_device_ctx),
        input_channels = {
            [name: str]: int = pin identifier and pin number
        }
        total_channels: int = max amount of channels allowed on each ioexpander (default 8)
    }

    """

    mcp: FakeMCP23017
    _identifier: str

    address: int  # hex address type is string in pinconfig.json
    input_channels: dict[str, int]  # {name: pin number}
    interrupt_pin: DigitalInputDevice = identifier(interrupt_pin_action.ctx)
    input_devices: list[IOExpanderInputDevice] = field(default_factory=list)

    # max amount of channels allowed on each ioexpander
    total_channels: int = 8


ctx = create_context("io_expander", IOExpander)


@device_parser(ctx)
def parse_io_expander(config: dict) -> IOExpander:
    if not "address" in config:
        raise ValueError("Missing address in config (io_expander.address)")
    hex_addr = int(config["address"], 16)
    mcp = MCP23017(busio.I2C(board.SCL, board.SDA), address=hex_addr)

    # https://docs.circuitpython.org/projects/mcp230xx/en/latest/examples.html#mcp230xx-event-detect-interrupt
    # Set up to check all the port B pins (pins 8-15) w/interrupts!
    mcp.interrupt_enable = 0xFFFF  # Enable Interrupts in all pins
    # If intcon is set to 0's we will get interrupts on
    # both button presses and button releases
    mcp.interrupt_configuration = 0x0000  # interrupt on any change
    mcp.io_control = 0x44  # Interrupt as open drain and mirrored
    mcp.clear_ints()  # Interrupts need to be cleared initially
    config["mcp"] = mcp

    expander = IOExpander(**config)
    expander.input_devices = [None] * expander.total_channels

    for name, num in expander.input_channels.items():
        pin = mcp.get_pin(num)
        pin.direction = FakeDirection.INPUT if is_dev() else Direction.INPUT
        pin.pull = FakePull.UP if is_dev() else Pull.UP
        device = IOExpanderInputDevice(pin, num, name)
        expander.input_devices[num] = device
        register_device(input_device_ctx, f"{expander._identifier}.{name}", device)

    def on_interrupt():
        logging.info("Interrupt triggered")
        for pin_flag in expander.mcp.int_flag:
            logging.info(f"pin_flag: {pin_flag}")
            if (
                (device := expander.input_devices[pin_flag])
                and device.value
                and device.when_activated
            ):
                device.when_activated()
            elif device and not device.value and device.when_deactivated:
                device.when_deactivated()
        expander.mcp.clear_ints()

    interrupt_pin_action.on_expander_activated(expander.interrupt_pin, on_interrupt)

    return expander
