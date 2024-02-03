from functools import wraps
from gpiozero import DigitalInputDevice

from utils.deviceMock import FakeInputDevice


pressure_pins = dict()


def register_pressure_pin(name: str, pressure) -> None:
    """
    Add a new pressure sensor to the list of pins.

    Args:
        name (str): the name of the pressure sensor
        pin (int): the pin number of the pressure sensor
    """
    if name in pressure_pins:
        raise ValueError(f"Pressure sensor {name} already exists")
    pressure_pins[name] = pressure


def get_pressure_device(name: str):
    """
    Get the pin number of a pressure sensor.

    Args:
        name (str): the name of the pressure sensor

    Returns:
        (int) the pin number of the pressure sensor
    """
    try:
        device = pressure_pins[name]
    except KeyError:
        raise KeyError(
            f"""
Pressure sensor {name} does not exist
Available pressure sensors: {list(pressure_pins.keys())}
            """
        )
    if device is None:
        raise ValueError(f"Pressure sensor {name} does not exist")
    return device


def get_pressure_names() -> list[str]:
    """
    Get a list of all the pressure sensor names.

    Returns:
        (list[str]) a list of all the pressure sensor names
    """
    return list(pressure_pins.keys())


def get_pressure_devices() -> list[int]:
    """
    Get a list of all the pressure sensor pins.

    Returns:
        (list[int]) a list of all the pressure sensor pins
    """
    return list(pressure_pins.values())


def pressure_action(func: callable) -> callable:
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
            name (str): the name of the pressure sensor
            args: the arguments to pass to the function
            kwargs: the keyword arguments to pass to the function
        """
        if len(args) < 1:
            raise ValueError("Missing argument")
        if (
            not isinstance(args[0], str)
            and not isinstance(args[0], DigitalInputDevice)
            and not isinstance(args[0], FakeInputDevice)
        ):
            raise ValueError("First argument must be a string or a DigitalOutputDevice")
        valve = get_pressure_device(args[0]) if isinstance(args[0], str) else args[0]
        return func(valve, *args[1:], **kwargs)

    return wrapper


@pressure_action
def is_pressure_ok(device) -> bool:
    """
    Check if the pressure sensor is ok.

    Args:
        name (str): the name of the pressure sensor

    Returns:
        (bool) true if the pressure sensor is ok, false otherwise
    """
    print("is_pressure_ok", device)
    return device.is_active


@pressure_action
def on_pressure_active(device, action: callable) -> None:
    """
    Add a new pressure sensor change event.

    Args:
        name (str): the name of the pressure sensor
        action (callable): the action to perform when the pressure sensor changes
    """
    if isinstance(device, str):
        return
    device.when_activated = action


@pressure_action
def on_pressure_deactive(device, action: callable) -> None:
    """
    Add a new pressure sensor change event.

    Args:
        name (str): the name of the pressure sensor
        action (callable): the action to perform when the pressure sensor changes
    """
    if isinstance(device, str):
        return
    device.when_deactivated = action
