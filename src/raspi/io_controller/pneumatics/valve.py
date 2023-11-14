from functools import wraps
from gpiozero import DigitalOutputDevice


type Valve = str | DigitalOutputDevice
valve_pins = dict()


def add_valve_pin(name: str, valve: DigitalOutputDevice) -> None:
    """
    Add a new valve pin to the list of pins.

    :param name: the name of the valve
    :param pin: the pin number of the valve
    """
    if name in valve_pins:
        raise ValueError(f"Valve {name} already exists")
    valve_pins[name] = valve


def get_valve(name: str) -> DigitalOutputDevice:
    """
    Get the pin number of a valve.

    :param name: the name of the valve
    :return: the pin number of the valve
    """
    return valve_pins[name]


def get_valve_names() -> list[str]:
    """
    Get a list of all the valve names.

    :return: a list of all the valve names
    """
    return list(valve_pins.keys())


def get_valve_pins() -> list[int]:
    """
    Get a list of all the valve pins.

    :return: a list of all the valve pins
    """
    return list(valve_pins.values())


def valve_action(func: callable) -> callable:
    """
    Decorator for valve actions.

    :param func: the function to decorate
    :return: the decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        """
        Decorated function.

        :param name: the name of the valve
        :param args: the arguments to pass to the function
        :param kwargs: the keyword arguments to pass to the function
        """
        if len(args) < 1:
            raise ValueError("Missing argument")
        if not isinstance(args[0], str) and not isinstance(
            args[0], DigitalOutputDevice
        ):
            raise ValueError("First argument must be a string or a DigitalOutputDevice")
        valve = get_valve(args[0]) if isinstance(args[0], str) else args[0]
        func(valve, *args[1:], **kwargs)

    return wrapper


@valve_action
def turn_valve_on(valve: Valve) -> None:
    """
    Turn a valve on.

    :param valve: the valve to turn on
    """
    valve.on()


@valve_action
def turn_valve_off(valve: Valve) -> None:
    """
    Turn a valve off.

    :param valve: the valve to turn off
    """
    valve.off()


@valve_action
def turn_value(valve: Valve, state: bool) -> None:
    """
    Turn a valve on or off.

    :param valve: the valve to turn on or off
    :param state: `True` to turn the valve on, `False` to turn it off
    """
    turn_valve_on(valve) if state else turn_valve_off(valve)


@valve_action
def toggle_valve(valve: Valve) -> None:
    """
    Toggle a valve.

    :param valve: the valve to toggle
    """
    turn_value(valve, not get_valve_state(valve))


@valve_action
def get_valve_state(valve: Valve) -> bool:
    """
    Get the state of a valve.

    :param valve: the valve to get the state of
    :return: `True` if the valve is on, `False` if it is off
    """
    return valve.value
