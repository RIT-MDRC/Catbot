import logging
from dataclasses import dataclass, field
from typing import Callable

import can

from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
)

DEFAULT_BUS_CONFIG = {
    "channel": "can0",
    "interface": "socketcan",
    "config_context": None,
    "ignore_config": False,
}


@device
@dataclass
class CanBus:
    silence: bool = field(default=False)  # silence received message log
    busConfig: dict = field(default_factory=dict)
    bus: can.Bus = None
    notifier: can.Notifier = None
    listeners: dict = field(default_factory=dict)

    def __post_init__(self):
        self.busConfig = {**DEFAULT_BUS_CONFIG, **self.busConfig}
        self.bus = self.bus if self.bus else can.Bus(**self.busConfig)
        self.notifier = (
            self.notifier
            if self.notifier
            else can.Notifier(self.bus, [lambda msg: read_message(self, msg)])
        )


def read_message(can_bus: CanBus, msg) -> None:
    axisId = msg.arbitration_id >> 5
    if not can_bus.silence:
        logging.info("Received message with id " + hex(msg.arbitration_id))
    if axisId in can_bus.listeners:
        can_bus.listeners[axisId](msg)
    else:
        logging.warning("Unhandled message with id " + hex(msg.arbitration_id))


ctx = create_generic_context("can_bus", [CanBus])


@device_parser(ctx)
def parse_can_bus(data: dict) -> CanBus:
    return CanBus(**data)


@device_action(ctx)
def send_message(
    bus: CanBus, arbitration_id: int, data, is_extended_id: bool = False
) -> bool:
    """Sends a message through the can bus. Returns whether the send was successful."""
    msg = can.Message(
        arbitration_id=arbitration_id, is_extended_id=is_extended_id, data=data
    )
    try:
        bus.bus.send(msg)
        return True
    except can.CanError:
        logging.error("Unable to send message on CAN bus.")
        return False


@device_action(ctx)
def send_message_recurring(
    bus: CanBus,
    arbitration_id: int,
    data,
    period: float,
    is_extended_id: bool = False,
    duration: float = None,
    modifier_callback: Callable[[object], None] = None,
) -> object:
    """Repeatedly sends a message through the can bus. Returns a task for it."""
    msg = can.Message(
        arbitration_id=arbitration_id, is_extended_id=is_extended_id, data=data
    )
    return bus.send_periodic(msg, period, duration, modifier_callback=modifier_callback)


@device_action(ctx)
def add_listener(bus: CanBus, axisID: int, callback: Callable[[object], None]) -> None:
    """Adds a listener to check for messages on a certain axis. There should be one listener per axis."""
    if axisID in bus.listeners:
        logging.warning(
            "Attempting to register multiple listeners for the same CAN Axis when only one allowed. Overriding old listener."
        )
    bus.listeners[axisID] = callback


@device_action(ctx)
def close(bus: CanBus) -> None:
    logging.info("Closing CAN Bus")
    bus.notifier.stop()
    bus.bus.shutdown()
