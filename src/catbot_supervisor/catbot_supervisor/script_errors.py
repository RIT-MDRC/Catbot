"""Explain the feedback condition that prevented a script from advancing."""

from catbot_supervisor.homing import ERROR_FIELDS


def clear_timeout_reason(body, names, timeout, fresh):
    prefix = f"Script step timed out: wait_clear ({timeout:g} s). "
    if not fresh:
        return prefix + "No fresh /body/state/error feedback; check Foundation and CAN."
    blocked = []
    for name in names:
        state = body.get(name)
        if state is None:
            blocked.append(f"{name}: missing motor status")
        elif not state.heartbeat_available:
            blocked.append(f"{name}: no fresh CAN heartbeat")
        elif state.axis_error_flags:
            faults = []
            for field in ERROR_FIELDS:
                value = getattr(state, field)
                if value:
                    labels = getattr(state, field.replace("_flags", "_messages"), ())
                    faults.append(
                        f"{field.removesuffix('_error_flags')}={value} [{', '.join(labels or ('UNDECODED',))}]"
                    )
            blocked.append(f"{name}: {', '.join(faults)}")
    if not blocked:
        return (
            prefix
            + "Clearance was not confirmed before the deadline; the latest report has no blocking axis faults."
        )
    return (
        prefix
        + "Motor errors did not clear: "
        + "; ".join(blocked)
        + ". Resolve these faults or missing heartbeats before retrying."
    )
