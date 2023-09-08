class Pressure():
    MIN_PRESSURE : float = 0.0  # todo: assign this
    MAX_PRESSURE : float = 0.0  # and this
    
    pressure : float = 0.0
    pressure_history : list[float] = []

    def __init__(self) -> None:
        ...

    def is_sufficient_pressure(self) -> bool:
        return False
    
    def get_average_pressure(self) -> float:
        return 0.0