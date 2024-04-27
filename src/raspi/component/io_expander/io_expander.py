from dataclasses import dataclass

import board
import busio
from adafruit_mcp230xx.mcp23017 import MCP23017, DigitalInOut
from component.smbus import smbus_actions
from digitalio import Direction, Pull
from gpiozero import DigitalInputDevice
from state_management import (
    create_context,
    device,
    device_action,
    device_parser,
    identifier,
    input_device_ctx,
)


class IOExpanderInputDevice:  # please feel free rename this if this is a bad name
    pin: DigitalInOut
    expander: "IOExpander"
    pin_num: int
    name: str
    addr: int

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


@device
@dataclass
class IOExpander:
    """
    16-bit I/O expander, currently only supports input devices.

    config schema:
    {
        address: str = i2c address of the device i.e. "0x20",
        interrupt_pin: DigitalInputDevice = identifier(input_device_ctx),
        input_devices = {
            [name: str]: int = pin identifier and pin number
        }
    }

    """

    mcp: MCP23017
    _identifier: str

    address: int  # hex address type is string in pinconfig.json
    input_devices: dict[str, int]  # {name: pin number}
    interrupt_pin: DigitalInputDevice = identifier(input_device_ctx)


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

    for name, num in enumerate(expander.input_devices):
        pin = mcp.get_pin(num)
        pin.direction = Direction.INPUT
        pin.pull = Pull.UP

    return expander
