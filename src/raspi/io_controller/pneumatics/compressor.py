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


@compressor_action
def turn_compressor_on(valve) -> None:
    """
    Turn a valve on.

    Args:
        valve (DigitalOutputDevice): the valve to turn on
    """
    valve.on()


@compressor_action
def turn_compressor_off(compressor) -> None:
    """
    Turn a valve off.

    Args:
        valve (DigitalOutputDevice): the valve to turn off
    """
    compressor.off()


@compressor_action
def turn_value(compressor, state: bool) -> None:
    """
    Turn a valve on or off.

    Args:
        valve (DigitalOutputDevice): the valve to turn on or off
        state (bool): `True` to turn the valve on, `False` to turn it off
    """
    turn_compressor_on(compressor) if state else turn_compressor_off(compressor)


@compressor_action
def toggle_valve(compressor) -> None:
    """
    Toggle a valve.

    Args:
        valve (DigitalOutputDevice): the valve to toggle
    """
    turn_value(compressor, not get_valve_state(compressor))


@compressor_action
def get_valve_state(compressor) -> bool:
    """
    Get the state of a valve.

    Args:
        valve (DigitalOutputDevice): the valve to get the state of

    Returns:
        (bool) `True` if the valve is on, `False` if it is off
    """
    return compressor.value
