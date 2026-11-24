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
        operation: str
        def __init__(self, **kwargs: object) -> None: ...
    class Response:
        success: bool
        message: str
        def __init__(self, **kwargs: object) -> None: ...

class GetSupervisorStatus:
    class Request:
        name: str
        def __init__(self, **kwargs: object) -> None: ...
    class Response:
        success: bool
        message: str
        status_json: str
        def __init__(self, **kwargs: object) -> None: ...

class RebootControllers:
    class Request:
        actuator_names: list[str]
        all_controllers: bool
        def __init__(self, **kwargs: object) -> None: ...
    class Response:
        success: bool
        message: str
        sent_boards: list[int]
        reconnected_boards: list[int]
        def __init__(self, **kwargs: object) -> None: ...
