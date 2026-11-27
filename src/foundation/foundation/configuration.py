"""Foundation-owned startup timing and freshness defaults."""

FOUNDATION_DEFAULTS = {
    "heartbeat_timeout_seconds": 0.5,
    "encoder_log_period_seconds": 1.0,
    "encoder_timeout_seconds": 0.25,
    "motor_arm_timeout_seconds": 0.5,
    "position_state_period_seconds": 0.02,
    "state_check_period_seconds": 0.05,
    "error_request_period_seconds": 1.0,
    "gain_update_period_seconds": 0.1,
    "gain_scale_step": 0.05,
    "limits_publish_period_seconds": 1.0,
}
