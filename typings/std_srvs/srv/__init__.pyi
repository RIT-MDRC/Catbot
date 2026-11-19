class Trigger:
    class Request:
        def __init__(self) -> None: ...
    class Response:
        success: bool
        message: str
        def __init__(self, **kwargs: object) -> None: ...
