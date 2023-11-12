from functools import wraps
from dataclasses import dataclass

from io.pneumatics.pressure import is_pressure_ok
from io.pneumatics.valve import get_valve_state, turn_valve_off, turn_valve_on

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

    Args:
        pressure (str): the name of the pressure sensor
        valve (str): the name of the valve
    """

    pressure: str
    valve: str


type Muscle = str | MuscleObj


def add_muscle(name: str, muscle: MuscleObj) -> None:
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
) -> MuscleObj:
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


def get_muscle_devices() -> list[MuscleObj]:
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

        :param name: the name of the muscle
        :param args: the arguments of the function
        :param kwargs: the keyword arguments of the function
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
def contract(muscle: Muscle, check: callable = is_pressure_ok) -> bool:
    """
    Contract a muscle.

    Args:
        muscle (Muscle): the muscle to contract
        check (callable): the function to check the pressure of the muscle (default: is_pressure_ok from io/pneumatics/pressure.py)

    Returns:
        True if the muscle was contracted, False otherwise
    """
    if not check(muscle.pressure):
        print("Pressure check failed, cannot contract muscle")
        return False
    return turn_valve_on(muscle.valve)


@muscle_action
def relax(muscle: Muscle, check: callable = get_valve_state) -> bool:
    """
    Relax a muscle.

    Args:
        muscle (Muscle): the muscle to relax
        check (callable): the function to check the state of the valve (default: get_valve_state from io/pneumatics/valve.py)
    """
    if not check(muscle.valve):
        print("Valve check failed, Muscle is already relaxed")
        return False
    return turn_valve_off(muscle.valve)
