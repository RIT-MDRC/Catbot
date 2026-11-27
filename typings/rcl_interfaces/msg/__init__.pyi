class SetParametersResult:
    successful: bool
    reason: str
    def __init__(self, *, successful: bool = False, reason: str = "") -> None: ...

class ParameterDescriptor:
    read_only: bool
    def __init__(self, *, read_only: bool = False, description: str = "") -> None: ...
