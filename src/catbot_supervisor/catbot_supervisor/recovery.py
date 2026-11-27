"""Validate a complete stopped roster before clearing all controller faults."""

from foundation.protocol import MotorState

from catbot_supervisor.homing import ERROR_FIELDS


def recovery_axes(body, names):
    if not names or set(body) != set(names):
        raise ValueError("Recovery requires the complete actuator state roster")
    for name in names:
        state = body[name]
        if not state.heartbeat_available:
            raise ValueError(f"Recovery requires a fresh heartbeat: {name}")
        if state.axis_state not in (
            MotorState.IDLE,
            MotorState.CLOSED_LOOP_CONTROL,
        ) or (
            any(getattr(state, field) for field in ERROR_FIELDS)
            and state.axis_state != MotorState.IDLE
        ):
            raise ValueError(f"Fault clearing requires a stopped axis: {name}")
    return tuple(names)
