from dataclasses import dataclass, field

from raspi.io_controller import pressure_actions, valve_actions

from ...io_controller.util.device import create_component_store


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


(muscle_action,) = create_component_store("muscle", [MuscleObj])
__all__ = ["contract", "relax", "toggle_muscle_state", "MuscleObj"]


@muscle_action
def contract(muscle: MuscleObj, check=pressure_actions.is_pressure_ok) -> bool:
    """
    Contract a muscle.

    Args:
        muscle (Muscle): the muscle to contract
        check (callable): the function to check the pressure (default: is_pressure_ok from pressure_actions)

    Returns:
        True if the muscle was contracted, False otherwise
    """
    if not check(muscle.pressure):
        print(f"{muscle.pressure}: Pressure check failed, cannot contract muscle")
        return False
    valve_actions.turn_valve_on(muscle.valve)
    return True


@muscle_action
def relax(muscle: MuscleObj, check=valve_actions.get_valve_state) -> bool:
    """
    Relax a muscle.

    Args:
        muscle (Muscle): the muscle to relax
        check (callable): the function to check the state of the valve (default: get_valve_state from valve_actions)
    """
    if not check(muscle.valve):
        print(f"{muscle.valve}: Valve check failed, Muscle is already relaxed")
        return False
    valve_actions.turn_valve_off(muscle.valve)
    return True


@muscle_action
def toggle_muscle_state(muscle: MuscleObj) -> bool:
    """
    Toggle a muscle.

    Args:
        muscle (Muscle): the muscle to toggle
    """
    is_contracted = valve_actions.get_valve_state(muscle.valve)
    if is_contracted:
        return relax(muscle)
    return contract(muscle)
