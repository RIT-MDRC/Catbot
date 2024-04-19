from dataclasses import dataclass
from adafruit_mcp230xx.mcp23017 import MCP23017
import board
import busio
from gpiozero import DigitalInputDevice

from component.smbus import smbus_actions
from state_management import (
    create_context,
    create_masked_context,
    device,
    device_action, 
    device_parser,
    identifier,
    input_device_ctx
)

limit_ctx = create_masked_context(input_device_ctx, "limit_interrupt")

@device_action(limit_ctx)
def is_limit_switch_active(device: DigitalInputDevice) -> bool:
    """
    Check if any limit switch connected to the device is currently enabled.

    [TODO: write the rest of these docs]
    """
    return device.is_active

@device_action(limit_ctx)
def on_limit_switch_state_change(device: DigitalInputDevice, action: callable) -> bool:
    device.when_activated = action

@device
@dataclass
class IOExpander:
    """
    16-bit I/O expander
    """
    address: int
    mcp: MCP23017
    _identifier: str

    def get_interrupt_switches(self):
        return self.mcp.int_flaga

ctx = create_context("io_expander", IOExpander)

@device_parser(ctx)
def parse_io_expander(config: dict) -> IOExpander:
    mcp = MCP23017(busio.I2C(board.SCL, board.SDA), address=0x20)
    config["mcp"] = mcp

    mcp.io_control = 0b0110010
    mcp.gppua = 0x00
    mcp.ipola = 0x00
    mcp.interrupt_enable = 0xff
    mcp.clear_ints()
    print(config)

    io_expander = IOExpander(**config)
    return io_expander