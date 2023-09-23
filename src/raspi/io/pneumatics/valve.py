class Valve():
    """
    TODO: this
    """
    def __init__(self) -> None:
        """
        Initialize a new instance of a Valve. There should only be one instance
        of this class for each real-world valve component.
        """
        ...

    def is_valve_open(self) -> bool:
        """
        Returns the current state of the valve.
        """
        return False
    
    def toggle_valve(self) -> None:
        """
        Open the valve if it is closed, and vice-versa.
        """
        ...

    def set_valve(self, state : bool) -> None:
        """
        Manually set the current state of the valve.

        :param state: `True` to open the valve, `False` to close it
        """
        ...