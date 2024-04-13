import logging
from dataclasses import dataclass
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
def on_limit_switch_activate(device: DigitalInputDevice, action: callable) -> bool:
    device.when_activated = action

@device_action(limit_ctx)
def on_limit_switch_deactivate(device: DigitalInputDevice, action: callable) -> bool:
    device.when_deactivated = action

@device
@dataclass
class IOExpander:
    """
    16-bit I/O expander
    """
    address: int
    _identifier: str
    i2c: smbus_actions.SMBus = identifier(smbus_actions.ctx)

    def read_data(self, register: list, start_register=0x00):
        """
        Get which limit switches are currently active, if any.
        """
        ...

ctx = create_context("io_expander", IOExpander)

@device_parser(ctx)
def parse_io_expander(config: dict):
    """
    TODO: write these docs
    """
    io_expander = IOExpander(**config)
    return io_expander