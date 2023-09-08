class Motor():
    pin : int
    current_value : float = 0.0
    min_value : float       # signal to rotate at max speed in one direction 
    middle_value : float    # signal to stop rotation
    max_value : float       # signal to rotate at max speed in other direction

    def __init__(self,
                 pin : int, 
                 min_value : float,
                 middle_value : float,
                 max_value : float) -> None:
        self.pin = pin
        self.min_value = min_value
        self.middle_value = middle_value
        self.max_value = max_value
        ...

    def send_signal(value : int) -> None:
        ...

    def run(direction : int, time : int) -> None:
        ...

    def run(direction : int) -> None:
        ...

    def stop() -> None:
        ...