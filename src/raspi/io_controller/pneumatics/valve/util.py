from functools import wraps

from gpiozero import DigitalOutputDevice

valve_pins = dict()


def register_valve_pin(name: str, valve) -> None:
    """
    Add a new valve pin to the list of pins.

    Args:
        name (str): the name of the valve
        pin (int): the pin number of the valve
    """
    if name in valve_pins:
        raise ValueError(f"Valve {name} already exists")
    valve_pins[name] = valve


def get_valve(name: str):
    """
    Get the pin number of a valve.

    Args:
        name (str): the name of the valve

    Returns:
        (int) the pin number of the valve
    """
    return valve_pins[name]


def get_valve_names() -> list[str]:
    """
    Get a list of all the valve names.

    Returns:
        (list[str]) a list of all the valve names
    """
    return list(valve_pins.keys())


def get_valve_pins() -> list[int]:
    """
    Get a list of all the valve pins.

    Returns:
        (list[int]) a list of all the valve pins
    """
    return list(valve_pins.values())


def valve_action(func: callable) -> callable:
    """
    Decorator for valve actions.

    Args:
        func (callable): the function to decorate

    Returns:
        (callable) the decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        """
        Decorated function.

        Args:
            name (str): the name of the valve
            args: the arguments to pass to the function
            kwargs: the keyword arguments to pass to the function
        """
        if len(args) < 1:
            raise ValueError("Missing argument")
        if not isinstance(args[0], str) and not isinstance(
            args[0], DigitalOutputDevice
        ):
            raise ValueError("First argument must be a string or a DigitalOutputDevice")
        valve = get_valve(args[0]) if isinstance(args[0], str) else args[0]
        return func(valve, *args[1:], **kwargs)

    return wrapper
