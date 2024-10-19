import can
import cantools
import math
import time
import logging
from dataclasses import dataclass

from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
)

@device
@dataclass(slots = True)
class CanBus:
    bus: can.Bus
    listeners: dict

    def __init__(self,channel = "can0",interface = "socketcan",config_context = None, ignore_config = False, **kwargs):
        self.bus = can.Bus(channel,interface,config_context,ignore_config,**kwargs)
        self.listeners = {}

ctx = create_generic_context("can_bus", [CanBus])

@device_parser(ctx)
def parse_can_bus(data: dict) -> CanBus:
    return CanBus(**data)

@device_action(ctx)
def send_message(bus: CanBus, arbitration_id: int, data, is_extended_id = False) -> bool:
    """Sends a message through the can bus. Returns whether the send was successful."""
    msg = can.Message(arbitration_id=arbitration_id, is_extended_id = is_extended_id, data = data)
    try:
        bus.send(msg)
        return True
    except can.CanError:
        return False

@device_action(ctx)
def add_listener(bus: CanBus, axisID: int, callback: callable[[object], None]) -> None:
    """Adds a listener to check for messages on a certain axis. There should be one listener per axis."""
    if axisID in bus.listeners:
        logging.warning("Attempting to register multiple listeners for the same CAN Axis when only one allowed. Overriding old listener.")
    bus.listeners[axisID] = callback

# TODO: Have this automatically happen in another thread and/or when a message is detected in the can bus, rather than needing to be called from the main code
@device_action(ctx)
def read_messages(can_bus: CanBus) -> None:
    msg = can_bus.bus.recv(timeout=0)
    while not msg is None:
        axisId = msg.arbitration_id >> 5
        if axisId in can_bus.listeners:
            can_bus.listeners[axisId](msg)
        else:
            logging.info("Unhandled message with id " + hex(msg.arbitration_id))
