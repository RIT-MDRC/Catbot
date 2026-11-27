import logging
import socket
import struct
import sys
import time
import typing
from dataclasses import dataclass, field

import can
from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
)

from foundation.protocol import COMMAND_BITS, COMMAND_MASK, HEARTBEAT_COMMAND

logger = logging.getLogger(__name__)
DEFAULT_BUS_CONFIG = {
    "channel": "can0",
    "interface": "socketcan",
    "config_context": None,
    "ignore_config": False,
}
USE: bool = False


@device
@dataclass
class CanBus:
    silence: bool = field(default=False)  # silence received message log
    busConfig: dict[str, typing.Any] = field(default_factory=dict)
    bus: can.BusABC = field(init=False)
    notifier: can.Notifier = field(init=False)
    listeners: dict = field(default_factory=dict)

    heartbeat_counts: dict[int, int] = field(
        default_factory=dict, init=False, repr=False
    )
    heartbeat_dispatch: dict[int, float] = field(
        default_factory=dict, init=False, repr=False
    )
    heartbeat_kernel: dict[int, float] = field(
        default_factory=dict, init=False, repr=False
    )
    tx_commands: dict[int, int] = field(default_factory=dict, init=False, repr=False)
    rx_count: int = field(default=0, init=False, repr=False)
    last_rx_monotonic: float | None = field(default=None, init=False, repr=False)
    last_kernel_timestamp: float = field(default=0.0, init=False, repr=False)
    peak_receive_lag: float = field(default=0.0, init=False, repr=False)
    peak_receive_lag_at: float | None = field(default=None, init=False, repr=False)
    last_callback_seconds: float = field(default=0.0, init=False, repr=False)
    peak_callback_seconds: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self):
        self.busConfig = {**DEFAULT_BUS_CONFIG, **self.busConfig}
        bus_factory = typing.cast(typing.Callable[..., can.BusABC], can.Bus)
        self.bus = bus_factory(**self.busConfig)
        self.notifier = can.Notifier(self.bus, [lambda msg: read_message(self, msg)])


def read_message(can_bus: CanBus, msg) -> None:
    started = time.monotonic()
    can_bus.rx_count += 1
    can_bus.last_rx_monotonic = started
    can_bus.last_kernel_timestamp = msg.timestamp
    if msg.timestamp > 0:
        lag = time.time() - msg.timestamp
        if lag > can_bus.peak_receive_lag:
            can_bus.peak_receive_lag, can_bus.peak_receive_lag_at = lag, started
    axisId = msg.arbitration_id >> COMMAND_BITS
    if msg.arbitration_id & COMMAND_MASK == HEARTBEAT_COMMAND:
        can_bus.heartbeat_counts[axisId] = can_bus.heartbeat_counts.get(axisId, 0) + 1
        can_bus.heartbeat_dispatch[axisId] = started
        can_bus.heartbeat_kernel[axisId] = msg.timestamp
    try:
        if not can_bus.silence:
            logger.info("Received message with id " + hex(msg.arbitration_id))
        if axisId in can_bus.listeners:
            can_bus.listeners[axisId](msg)
        else:
            logger.warning("Unhandled message with id " + hex(msg.arbitration_id))
    finally:
        elapsed = time.monotonic() - started
        can_bus.last_callback_seconds = elapsed
        can_bus.peak_callback_seconds = max(can_bus.peak_callback_seconds, elapsed)


ctx = create_generic_context("can_bus", [CanBus])


@device_parser(ctx)
def parse_can_bus(data: dict) -> CanBus:
    return CanBus(**data)


def get_names() -> tuple[str, ...]:
    """Return configured CAN bus component names."""
    return tuple(ctx.store)


def socket_memory_health(sock):
    """Read Linux socket memory/drop counters without receiving or opening sockets."""
    if sock is None or sys.platform != "linux":
        return None
    try:
        # Linux UAPI: asm-generic/socket.h SO_MEMINFO; linux/sock_diag.h SK_MEMINFO_*.
        values = struct.unpack(
            "=9I",
            sock.getsockopt(socket.SOL_SOCKET, getattr(socket, "SO_MEMINFO", 55), 36),
        )
    except (OSError, struct.error):
        return None
    return {
        "receive_allocated_bytes": values[0],
        "receive_limit_bytes": values[1],
        "backlog_bytes": values[7],
        "drops_total": values[8],
    }


@device_action(ctx)
def get_receive_health(bus: CanBus) -> dict:
    """Read existing receiver metrics; never opens another CAN socket."""
    now = time.monotonic()
    received = bus.last_rx_monotonic
    lag = None
    if received is not None and bus.last_kernel_timestamp > 0:
        lag = (time.time() - (now - received) - bus.last_kernel_timestamp) * 1000
    error = bus.notifier.exception
    sock = getattr(bus.bus, "socket", None)
    try:
        receive_buffer = (
            sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            if sock is not None
            else None
        )
    except OSError:
        receive_buffer = None
    return {
        "frames_processed": bus.rx_count,
        "tx_commands_accepted": {
            hex(command): count
            for command, count in getattr(bus, "tx_commands", {}).items()
        },
        "heartbeat_processed": {
            axis: {
                "count": count,
                "dispatch_age_ms": (now - bus.heartbeat_dispatch[axis]) * 1000,
                "kernel_to_callback_ms": (
                    time.time()
                    - (now - bus.heartbeat_dispatch[axis])
                    - bus.heartbeat_kernel[axis]
                )
                * 1000,
            }
            for axis, count in bus.heartbeat_counts.items()
        },
        "last_dispatch_age_ms": None if received is None else (now - received) * 1000,
        "kernel_to_callback_ms": lag,
        "peak_kernel_to_callback_ms": bus.peak_receive_lag * 1000,
        "peak_receive_lag_at_monotonic": bus.peak_receive_lag_at,
        "last_callback_ms": bus.last_callback_seconds * 1000,
        "peak_callback_ms": bus.peak_callback_seconds * 1000,
        "notifier_error": None if error is None else repr(error),
        "socket_receive_buffer_bytes": receive_buffer,
        "socket_memory": socket_memory_health(sock),
    }


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
        counts = getattr(bus, "tx_commands", None)
        if counts is None:
            counts = bus.tx_commands = {}
        command = arbitration_id & COMMAND_MASK
        counts[command] = counts.get(command, 0) + 1
        return True
    except (can.CanError, OSError):
        logger.error("Unable to send message on CAN bus.")
        return False


@device_action(ctx)
def request_message(
    bus: CanBus,
    arbitration_id: int,
    dlc: int = 8,
    is_extended_id: bool = False,
) -> bool:
    """Request one CANSimple ``Get_`` response using a remote frame."""
    msg = can.Message(
        arbitration_id=arbitration_id,
        is_extended_id=is_extended_id,
        is_remote_frame=True,
        dlc=dlc,
    )
    try:
        bus.bus.send(msg)
        return True
    except (can.CanError, OSError):
        logger.error("Unable to request message on CAN bus.")
        return False


@device_action(ctx)
def send_message_recurring(
    bus: CanBus,
    arbitration_id: int,
    data,
    period: float,
    is_extended_id: bool = False,
    duration: float | None = None,
    modifier_callback: typing.Callable[[object], None] | None = None,
) -> object:
    """Repeatedly sends a message through the can bus. Returns a task for it."""
    msg = can.Message(
        arbitration_id=arbitration_id, is_extended_id=is_extended_id, data=data
    )
    return bus.bus.send_periodic(
        msg, period, duration, modifier_callback=modifier_callback
    )


@device_action(ctx)
def add_listener(
    bus: CanBus, axisID: int, callback: typing.Callable[[object], None]
) -> None:
    """Adds a listener to check for messages on a certain axis. There should be one listener per axis."""
    if axisID in bus.listeners:
        logger.warning(
            "Attempting to register multiple listeners for the same CAN Axis when only one allowed. Overriding old listener."
        )
    bus.listeners[axisID] = callback


@device_action(ctx)
def close(bus: CanBus) -> None:
    logger.info("Closing CAN Bus")
    bus.notifier.stop()
    bus.bus.shutdown()
