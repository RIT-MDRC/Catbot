from functools import wraps

from gpiozero import DigitalOutputDevice

compressor_pins = dict()


def register_compressor_pin(name: str, compressor) -> None:
    """
    Add a new valve pin to the list of pins.

    Args:
        name (str): the name of the valve
        pin (int): the pin number of the valve
    """
    if name in compressor_pins:
        raise ValueError(f"Compressor {name} already exists")
    compressor_pins[name] = compressor


def get_compressor(name: str):
    """
    Get the pin number of a valve.

    Args:
        name (str): the name of the valve

    Returns:
        (int) the pin number of the valve
    """
    return compressor_pins[name]


def get_compressor_names() -> list[str]:
    """
    Get a list of all the valve names.

    Returns:
        (list[str]) a list of all the valve names
    """
    return list(compressor_pins.keys())


def get_compressor_pins() -> list[int]:
    """
    Get a list of all the valve pins.

    Returns:
        (list[int]) a list of all the valve pins
    """
    return list(compressor_pins.values())


def compressor_action(func: callable) -> callable:
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
            args (list): the arguments to pass to the function
            kwargs (dict): the keyword arguments to pass to the function
        """
        if len(args) < 1:
            raise ValueError("Missing argument")
        if not isinstance(args[0], str) and not isinstance(
            args[0], DigitalOutputDevice
        ):
            raise ValueError("First argument must be a string or a DigitalOutputDevice")
        valve = get_compressor(args[0]) if isinstance(args[0], str) else args[0]
        return func(valve, *args[1:], **kwargs)

    return wrapper
