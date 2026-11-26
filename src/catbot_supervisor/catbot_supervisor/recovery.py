"""Select only stopped axes whose sole faults are latched endstop events."""

from catbot_supervisor.homing import ERROR_FIELDS, actuator_details

ENDSTOP_ERRORS = 4096 | 8192


def endstop_axes(body, names):
    if set(body) != set(names):
        raise ValueError("Recovery requires the complete actuator state roster")
    selected = []
    for name in names:
        state = body[name]
        if not state.heartbeat_available:
            raise ValueError(f"Recovery requires a fresh heartbeat: {name}")
        if state.axis_error_flags & ~ENDSTOP_ERRORS or any(
            getattr(state, field) for field in ERROR_FIELDS[1:]
        ):
            raise ValueError(
                f"Recovery requires resolving actuator fault: {name} ({actuator_details(state)})"
            )
        if state.axis_error_flags:
            if state.axis_state != 1:
                raise ValueError(f"Endstop recovery requires idle axis: {name}")
            selected.append(name)
    return tuple(selected)
