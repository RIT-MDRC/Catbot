from functools import wraps
from dataclasses import dataclass, field

from io_controller.pneumatics.pressure import is_pressure_ok
from io_controller.pneumatics.valve import (
    get_valve_state,
    turn_valve_off,
    turn_valve_on,
)

muscles = dict()


@dataclass(slots=True)
class MuscleObj:
    """
    Dataclass for a muscle.
    \nhow to use dataclass:
    ```
    muscle = MuscleObj(pressure="pressure_name", valve="valve_name")
    print(muscle.pressure) // "pressure_name"
    ```
    \nhow not to use dataclass:
    ```
    muscle.pressure.get_pressure()
    muscle.valve.turn_valve_on()
    ```
    \n remember that the dataclass should not contain any logic, only data.
    Args:
        pressure (str): the name of the pressure sensor
        valve (str): the name of the valve
    """

    pressure: str = field(default="not_set")
    valve: str = field(default="not_set")

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


def add_muscle(name: str, muscle) -> None:
    """
    Add a new muscle to the list of pins.

    Args:
        name (str): the name of the muscle
        muscle (MuscleObj): the muscle dataclass object
    """
    if name in muscles:
        raise ValueError(f"Muscle {name} already exists")
    muscles[name] = muscle


def get_muscle(
    name: str,
):
    """
    Get the pin number of a muscle.

    Args:
        name (str): the name of the muscle

    Returns:
        (MuscleObj) muscle dataclass object
    """
    return muscles[name]


def get_muscle_names() -> list[str]:
    """
    Get a list of all the muscle names.

    Returns:
        a list of all the muscle names
    """
    return list(muscles.keys())


def get_muscle_devices():
    """
    Get a list of all the muscle pins.

    Returns:
        a list of all the muscle pins
    """
    return list(muscles.values())


def muscle_action(func: callable) -> callable:
    """
    Decorator for muscle actions.

    Args:
        func (callable): the function to decorate

    Returns:
        the decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> bool:
        """
        Decorated function.

        Args:
            args: the arguments of the function
            kwargs: the keyword arguments of the function
        """
        if len(args) == 0:
            raise ValueError("Muscle name not provided")
        if not isinstance(args[0], str) and not isinstance(args[0], MuscleObj):
            raise ValueError("Muscle name must be a string or a MuscleObj")
        muscle = get_muscle(args[0]) if isinstance(args[0], str) else args[0]
        res = func(muscle, *args[1:], **kwargs)
        if res is None:
            return True
        return res

    return wrapper


@muscle_action
def contract(muscle) -> bool:
    """
    Contract a muscle.

    Args:
        muscle (Muscle): the muscle to contract

    Returns:
        True if the muscle was contracted, False otherwise
    """
    pressure = is_pressure_ok(muscle.pressure)
    if pressure:
        print(f"{muscle.pressure}: Pressure check failed, cannot contract muscle")
        return False
    print("contracting muscle")
    turn_valve_on(muscle.valve)
    return True


@muscle_action
def relax(muscle) -> bool:
    """
    Relax a muscle.

    Args:
        muscle (Muscle): the muscle to relax
        check (callable): the function to check the state of the valve (default: get_valve_state from io/pneumatics/valve.py)
    """
    check = not get_valve_state(muscle.valve)
    if check:
        print(f"{muscle.valve}: Valve check failed, Muscle is already relaxed")
        return False
    print("relaxing muscle")
    turn_valve_off(muscle.valve)
    return True


@muscle_action
def toggle_muscle_state(muscle) -> bool:
    """
    Toggle a muscle.

    Args:
        muscle (Muscle): the muscle to toggle
    """
    is_contracted = get_valve_state(muscle.valve)
    if is_contracted:
        return relax(muscle)
    return contract(muscle)


def noop(*args, **kwargs) -> bool:
    """
    No operation function.
    Pass into check if you want to disable the check.
    """
    return True
