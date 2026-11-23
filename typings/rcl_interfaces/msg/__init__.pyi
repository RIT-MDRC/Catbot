class SetParametersResult:
    successful: bool
    reason: str
    def __init__(self, *, successful: bool = False, reason: str = "") -> None: ...
