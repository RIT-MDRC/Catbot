"""Feedback checks for the fault-intolerant robot homing sequence."""

import math

ERROR_FIELDS = (
    "axis_error_flags",
    "motor_error_flags",
    "encoder_error_flags",
    "sensorless_error_flags",
    "controller_error_flags",
)


def fault_reason(body, names):
    if set(body) != set(names):
        return "Homing requires the complete actuator state roster"
    for name in names:
        state = body[name]
        if not state.heartbeat_available:
            return f"Homing requires a fresh heartbeat for {name}"
        for field in ERROR_FIELDS:
            if getattr(state, field):
                return f"Homing stopped: {name} {field}={getattr(state, field)}"
    return ""


class StateCycle:
    """Observe every requested axis become active, then all return to idle."""

    def __init__(self, names, state):
        self.names, self.state = tuple(names), state
        # FULL_CALIBRATION_SEQUENCE expands into these tasks in ODrive 0.5.6.
        self.active_states = {3, 4, 6, 7, 12, 13} if state == 3 else {state}
        self.started = set()

    def observe(self, body):
        for name in self.names:
            sample = body.get(name)
            if (
                sample is not None
                and sample.heartbeat_available
                and sample.axis_state in self.active_states
            ):
                self.started.add(name)

    def complete(self, body):
        samples = {name: body[name] for name in self.names if name in body}
        reason = fault_reason(samples, self.names)
        if reason:
            raise RuntimeError(reason)
        self.observe(samples)
        return self.started == set(self.names) and all(
            sample.axis_state == 1 for sample in samples.values()
        )


def at_position(body, names, targets):
    if len(names) != len(targets) or not names:
        return False
    for name, target in zip(names, targets):
        state = body.get(name)
        if state is None or not state.valid:
            return False
        position, velocity = state.position_degrees, state.velocity_degrees_per_second
        if not all(math.isfinite(v) for v in (position, velocity, target)):
            return False
        if abs(position - target) > 1.0 or abs(velocity) > 1.0:
            return False
    return True
