"""Pi operational limits, separate from Orin settings and hardware protocol data."""

import math
from dataclasses import dataclass, fields, replace

from foundation.protocol import MotorState

from catbot_supervisor.core import Limits


@dataclass(frozen=True)
class OperationalSettings:
    tick_period_seconds: float = 0.02
    probe_period_seconds: float = 0.1
    health_period_seconds: float = 1.0
    recovery_timeout_seconds: float = 3.0
    emergency_retry_seconds: float = 1.0
    remote_stop_retry_seconds: float = 1.0
    compute_warning_interval_seconds: float = 30.0
    shutdown_timeout_seconds: float = 3.0
    position_tolerance_degrees: float = 1.0
    velocity_tolerance_degrees_s: float = 1.0
    script_step_timeout_seconds: float = 3.0
    clear_errors_timeout_seconds: float = 3.0
    state_transition_timeout_seconds: float = 3.0
    arm_timeout_seconds: float = 3.0
    zero_ready_timeout_seconds: float = 5.0
    position_move_timeout_seconds: float = 15.0
    homing_timeout_seconds: float = 30.0
    calibration_timeout_seconds: float = 60.0
    operator_timeout_seconds: float = 120.0
    homing_delay_seconds: float = 15.0
    policy_startup_timeout_seconds: float = 120.0
    policy_stop_timeout_seconds: float = 8.0
    health_wait_timeout_seconds: float = 5.0
    job_restart_timeout_seconds: float = 8.0
    front_flexion_clearance_degrees: float = 30.0

    def __post_init__(self):
        validate_positive(vars(self))

    def step(self, step):
        """Apply the configured budgets to built-in script steps."""
        key = {
            "wait_clear": "clear_errors_timeout_seconds",
            "wait_position": "position_move_timeout_seconds",
            "wait_operator": "operator_timeout_seconds",
            "delay": "homing_delay_seconds",
            "wait_preflight": "policy_startup_timeout_seconds",
            "wait_policy_ready": "policy_startup_timeout_seconds",
            "wait_link": "policy_startup_timeout_seconds",
            "wait_policy_stopped": "policy_stop_timeout_seconds",
            "wait_health": "health_wait_timeout_seconds",
            "job_restart": "job_restart_timeout_seconds",
        }.get(step.kind)
        if step.kind == "wait_cycle":
            key = (
                "calibration_timeout_seconds"
                if step.state == MotorState.FULL_CALIBRATION_SEQUENCE
                else "homing_timeout_seconds"
            )
        elif step.kind == "wait_state":
            key = (
                "homing_timeout_seconds"
                if step.timeout == 30.0
                else "state_transition_timeout_seconds"
            )
        elif step.kind == "wait_ready":
            key = (
                "zero_ready_timeout_seconds"
                if step.timeout == 5.0
                else "arm_timeout_seconds"
            )
        if key is None:
            key = "script_step_timeout_seconds"
        return replace(step, timeout=getattr(self, key))


def validate_positive(values):
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be positive and finite")


OPERATIONAL_DEFAULTS = {
    field.name: field.default for field in fields(OperationalSettings)
}
RPI_DEFAULTS = {
    **vars(Limits()),
    **OPERATIONAL_DEFAULTS,
    "body_timeout": 0.5,
    "min_cpu_headroom_percent": 10.0,
    "max_temperature_c": 80.0,
    "heartbeat_recovery_seconds": 1.0,
    "controller_reconnect_timeout": 10.0,
}
