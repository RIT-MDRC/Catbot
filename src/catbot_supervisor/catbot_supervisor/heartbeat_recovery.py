"""Stable recovery eligibility for communication-only emergencies."""

import math


class HeartbeatRecovery:
    def __init__(self, stable_seconds=1.0):
        if not math.isfinite(stable_seconds) or stable_seconds <= 0:
            raise ValueError("heartbeat_recovery_seconds must be positive and finite")
        self.stable_seconds = stable_seconds
        self.kind = None
        self.healthy_since = None

    def start(self, reason):
        self.kind = (
            "motor"
            if reason.startswith("Foundation actuator heartbeat unavailable:")
            else "orin"
            if reason
            in (
                "Orin heartbeat lost",
                "Link or Foundation lost during script: Orin heartbeat lost",
            )
            else None
        )
        self.healthy_since = None

    def ready(self, now, healthy, faulted=False):
        if faulted:
            self.kind = None
        if self.kind is None or not healthy:
            self.healthy_since = None
            return False
        if self.healthy_since is None:
            self.healthy_since = now
        if now - self.healthy_since < self.stable_seconds:
            return False
        self.kind = None
        self.healthy_since = None
        return True
