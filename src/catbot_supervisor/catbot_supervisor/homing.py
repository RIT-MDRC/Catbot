"""Feedback checks for the fault-intolerant robot homing sequence."""

import math

ERROR_FIELDS = (
    "axis_error_flags",
    "motor_error_flags",
    "encoder_error_flags",
    "sensorless_error_flags",
    "controller_error_flags",
)


def actuator_details(state):
    """Keep the raw masks and Foundation's decoded flags in supervisor errors."""
    details = [
        f"axis_state={state.axis_state}",
        f"heartbeat_available={state.heartbeat_available}",
    ]
    for field in ERROR_FIELDS:
        value = getattr(state, field)
        messages = getattr(state, field.replace("_flags", "_messages"), ())
        labels = (messages or ("UNDECODED",)) if value else ("NONE",)
        details.append(f"{field}={value} [{', '.join(labels)}]")
    return ", ".join(details)


def readiness_reason(body):
    unavailable = [
        f"{name} ({actuator_details(state)})"
        for name, state in body.items()
        if not state.ready
    ]
    return (
        "Foundation actuator not ready: " + "; ".join(unavailable)
        if unavailable
        else ""
    )


def fault_reason(body, names):
    if set(body) != set(names):
        return "Foundation requires the complete actuator state roster"
    for name in names:
        state = body[name]
        if not state.heartbeat_available:
            return (
                f"Foundation actuator heartbeat unavailable: {name} "
                f"({actuator_details(state)})"
            )
        if any(getattr(state, field) for field in ERROR_FIELDS):
            return f"Foundation actuator fault: {name} ({actuator_details(state)})"
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
