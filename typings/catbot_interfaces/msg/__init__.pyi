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

