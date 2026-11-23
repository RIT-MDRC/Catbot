"""Deterministic Pi decisions. All deadlines use the Pi monotonic clock."""

import math
from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    BOOT = "boot"
    IDLE = "idle"
    READY = "ready"
    HOLDING = "holding"
    RUNNING = "running"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class Limits:
    action_age: float = 0.25
    heartbeat_age: float = 0.5
    max_rtt: float = 0.15
    max_jitter: float = 0.05
    future_tolerance: float = 0.02

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in vars(self).values()):
            raise ValueError("Link limits must be positive and finite")


def status_sequence(value):
    return status_uint64(value)


def status_uint32(value):
    try:
        integer = int(value)
        if integer < 0:
            return 0
        return integer if integer <= 0xFFFFFFFF else 0xFFFFFFFF
    except (TypeError, ValueError, OverflowError):
        return 0


def status_uint64(value):
    try:
        integer = int(value)
        if integer < 0:
            return 0
        return integer if integer <= 0xFFFFFFFFFFFFFFFF else 0xFFFFFFFFFFFFFFFF
    except (TypeError, ValueError, OverflowError):
        return 0


def status_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def status_string(value):
    return "" if value is None else str(value)


def status_bool(value):
    if isinstance(value, bool):
        return value
    return bool(value)


class ActionGate:
    def __init__(self, limits=None):
        self.limits = limits or Limits()
        self.mode = Mode.BOOT
        self.reason = "boot"
        self.session = ""
        self.heartbeat_sequence = -1
        self.action_sequence = None
        self.heartbeat_at = None
        self.action_at = None
        self.action_stamp = None
        self.orin_degraded = True
        self.rtt = None
        self.jitter = 0.0
        self.probe_at = None
        self.probes = {}
        self.probe_sequence = 0

    def probe(self, now):
        self.probe_sequence += 1
        self.probes = {
            k: v for k, v in self.probes.items() if now - v <= self.limits.heartbeat_age
        }
        self.probes[self.probe_sequence] = now
        return self.probe_sequence

    def trip(self, reason):
        if self.mode not in (Mode.EMERGENCY, Mode.SHUTDOWN, Mode.HOLDING):
            self.reason = reason
        if self.mode in (Mode.READY, Mode.RUNNING):
            self.mode = Mode.DEGRADED
        return False

    def heartbeat(self, session, sequence, degraded, probe_id, now):
        if not session or sequence <= 0:
            return self.trip("missing Orin session")
        if self.session and session != self.session:
            if self.mode in (Mode.READY, Mode.RUNNING, Mode.DEGRADED, Mode.EMERGENCY):
                return self.trip("Orin session changed; explicit recovery required")
            self.heartbeat_sequence = -1
            self.action_sequence = self.action_at = self.action_stamp = None
            self.rtt = self.probe_at = None
            self.jitter = 0.0
        if sequence <= self.heartbeat_sequence:
            return self.trip("replayed Orin heartbeat")
        self.session = session
        self.heartbeat_sequence = sequence
        self.heartbeat_at = now
        self.orin_degraded = degraded
        sent = self.probes.pop(probe_id, None)
        if sent is not None:
            sample = now - sent
            if self.rtt is not None:
                self.jitter = 0.8 * self.jitter + 0.2 * abs(sample - self.rtt)
            self.rtt, self.probe_at = sample, now
        return self.check(now, require_action=False)

    def check(self, now, require_action=True):
        if (
            self.heartbeat_at is None
            or not 0 <= now - self.heartbeat_at <= self.limits.heartbeat_age
        ):
            return self.trip("Orin heartbeat lost")
        if self.orin_degraded:
            return self.trip("Orin reported degraded")
        if (
            self.probe_at is None
            or not 0 <= now - self.probe_at <= self.limits.heartbeat_age
        ):
            return self.trip("Orin probe echo lost")
        if (
            self.rtt is None
            or self.rtt > self.limits.max_rtt
            or self.jitter > self.limits.max_jitter
        ):
            return self.trip("Orin RTT or jitter exceeds limit")
        if require_action and (
            self.action_at is None
            or not 0 <= now - self.action_at <= self.limits.action_age
        ):
            return self.trip("Orin action stream stale")
        if self.mode not in (Mode.EMERGENCY, Mode.SHUTDOWN):
            self.reason = "healthy"
        return True

    def action(self, session, sequence, stamp, wall_now, now, names, positions):
        if self.mode in (Mode.EMERGENCY, Mode.SHUTDOWN, Mode.DEGRADED):
            return False
        if not self.check(now, require_action=False):
            return False
        if session != self.session:
            return self.trip("action session mismatch")
        if sequence <= 0:
            return self.trip("invalid action sequence")
        if self.action_sequence is not None and sequence != self.action_sequence + 1:
            return self.trip("action out of sequence")
        age = wall_now - stamp
        if (
            not math.isfinite(age)
            or not -self.limits.future_tolerance <= age <= self.limits.action_age
        ):
            return self.trip("stale action or unsynchronized ROS clocks")
        if self.action_stamp is not None and stamp < self.action_stamp:
            return self.trip("action timestamp regressed")
        if (
            not names
            or len(names) != len(positions)
            or len(set(names)) != len(names)
            or any(not math.isfinite(v) for v in positions)
        ):
            return self.trip("malformed policy action")
        self.action_sequence, self.action_at, self.action_stamp = sequence, now, stamp
        return self.mode == Mode.RUNNING

    def start(self, now):
        if self.mode not in (Mode.READY, Mode.HOLDING):
            raise ValueError("Robot must be ready or holding before running")
        if not self.check(now):
            if self.mode == Mode.HOLDING:
                raise ValueError(
                    "Policy control requires a healthy Orin link and fresh actions"
                )
            raise ValueError(self.reason)
        self.mode = Mode.RUNNING

    def emergency(self, reason):
        self.mode, self.reason = Mode.EMERGENCY, reason

    def recover(self):
        if self.mode != Mode.EMERGENCY:
            raise ValueError("Recovery requires emergency mode")
        probe_sequence = self.probe_sequence
        self.__init__(self.limits)
        self.probe_sequence = probe_sequence
        self.mode = Mode.IDLE
        self.reason = "recovered; explicit startup required"
