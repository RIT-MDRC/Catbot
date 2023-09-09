class Pressure():
    """
    Represents air pressure readings to measure current flexion/extension
    (knee) movement of each leg.
    """
    MIN_PRESSURE : float = 0.0  # TODO: assign this
    MAX_PRESSURE : float = 0.0  # and this
    
    pressure : float = 0.0
    pressure_history : list[float] = []

    def __init__(self) -> None:
        ...

    def is_sufficient_pressure(self) -> bool:
        """
        TODO: this one
        """
        return False
    
    def get_average_pressure(self) -> float:
        """
        Gets average pressure reading from the logged history of previous
        readings.
        """
        return 0.0