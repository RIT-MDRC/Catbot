class MotorCommand:
    class Request:
        actuator_names: list[str]
        operation: str
        state: int
        def __init__(self, **kwargs: object) -> None: ...
    class Response:
        success: bool
        message: str
        def __init__(self, **kwargs: object) -> None: ...

class RunScript:
    class Request:
        name: str
        def __init__(self, **kwargs: object) -> None: ...
    class Response:
        success: bool
        message: str
        def __init__(self, **kwargs: object) -> None: ...

class SupervisorJob:
    class Request:
        name: str
        start: bool
        def __init__(self, **kwargs: object) -> None: ...
    class Response:
        success: bool
        message: str
        def __init__(self, **kwargs: object) -> None: ...
