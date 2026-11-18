"""Type declarations matching the messages in ``src/catbot_interfaces/msg``."""

from builtin_interfaces.msg import Time

class ActuatorErrorState:
    actuator_name: str
    axis_id: int
    heartbeat_available: bool
    ready: bool
    axis_state: int
    axis_error_flags: int
    axis_error_messages: list[str]
    motor_error_flags: int
    motor_error_messages: list[str]
    encoder_error_flags: int
    encoder_error_messages: list[str]
    sensorless_error_flags: int
    sensorless_error_messages: list[str]
    controller_error_flags: int
    controller_error_messages: list[str]
    def __init__(self, **kwargs: object) -> None: ...

class ActuatorKinematicState:
    actuator_name: str
    axis_id: int
    valid: bool
    position_degrees: float
    velocity_degrees_per_second: float
    def __init__(self, **kwargs: object) -> None: ...

class ActuatorPositionCommand:
    actuator_names: list[str]
    positions_degrees: list[float]
    def __init__(self, **kwargs: object) -> None: ...

class BodyErrorState:
    stamp: Time
    actuators: list[ActuatorErrorState]
    def __init__(self, **kwargs: object) -> None: ...

class BodyKinematicState:
    stamp: Time
    actuators: list[ActuatorKinematicState]
    def __init__(self, **kwargs: object) -> None: ...

class PolicyFeedback:
    stamp: Time
    base_height_quaternion: list[float]
    heading_linear_velocity: list[float]
    base_angular_velocity: list[float]
    joint_positions: list[float]
    joint_velocities: list[float]
    normalized_air_time: list[float]
    previous_contact: list[bool]
    has_stance: list[bool]
    motion_travel: list[float]
    motion_progress: float
    def __init__(self, **kwargs: object) -> None: ...


class PolicyMetrics:
    stamp: Time
    device: str
    window_seconds: float
    control_interval_ms: float
    published_hz: float
    sample_count: int
    inference_p50_ms: float
    inference_p95_ms: float
    inference_p99_ms: float
    round_trip_p50_ms: float
    round_trip_p95_ms: float
    round_trip_p99_ms: float
    feedback_age_p50_ms: float
    feedback_age_p95_ms: float
    feedback_age_p99_ms: float
    missed_timer_intervals: int
    busy_ticks: int
    discarded_results: int
    adapter_cpu_percent_one_core: float
    adapter_peak_rss_kib: int
    worker_cpu_percent_one_core: float
    worker_peak_rss_kib: float
    def __init__(self, **kwargs: object) -> None: ...

class PolicyAction:
    stamp: Time
    session: str
    sequence: int
    command: ActuatorPositionCommand
    def __init__(self, **kwargs: object) -> None: ...

class PolicyActionAck:
    session: str
    sequence: int
    forwarded: bool
    def __init__(self, **kwargs: object) -> None: ...

class OrinHeartbeat:
    stamp: Time
    session: str
    sequence: int
    action_sequence: int
    probe_id: int
    policy_active: bool
    degraded: bool
    reason: str
    def __init__(self, **kwargs: object) -> None: ...
