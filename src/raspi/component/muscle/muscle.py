import logging
from dataclasses import dataclass

from gpiozero import DigitalInputDevice, DigitalOutputDevice
from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from .pneumatics import pressure_actions, valve_actions


@device
@dataclass(slots=True)
class MuscleObj:
    """
    Args:
        pressure (str): the name of the pressure sensor
        valve (str): the name of the valve
    """

    pressure: DigitalInputDevice = identifier(pressure_actions.ctx)
    valve: DigitalOutputDevice = identifier(valve_actions.ctx)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


ctx = create_generic_context("muscle", [MuscleObj])


@device_parser(ctx)
def parse_muscle(data: dict) -> MuscleObj:
    """
    Parse a muscle from a dictionary.

    Args:
        data (dict): the dictionary to parse

    Returns:
        (Muscle) the parsed muscle
    """
    return MuscleObj(**data)


@device_action(ctx)
def contract(muscle: MuscleObj, check=pressure_actions.is_pressure_ok) -> bool:
    """
    Contract a muscle.

    Args:
        muscle (Muscle): the muscle to contract
        check (callable): the function to check the pressure (default: is_pressure_ok from pressure_actions)

    Returns:
        True if the muscle was contracted, False otherwise
    """
    logging.info("Contracting muscle %s", muscle)
    if not check(muscle.pressure):
        logging.warning(
            f"{muscle.pressure}: Pressure check failed, cannot contract muscle"
        )
        return False
    valve_actions.turn_valve_on(muscle.valve)
    return True


@device_action(ctx)
def relax(muscle: MuscleObj, check=valve_actions.get_valve_state) -> bool:
    """
    Relax a muscle.

    Args:
        muscle (Muscle): the muscle to relax
        check (callable): the function to check the state of the valve (default: get_valve_state from valve_actions)

    Returns:
        True if the muscle was relaxed, False otherwise
    """
    logging.info("relaxing muscle %s", muscle)
    if not check(muscle.valve):
        logging.warning(
            f"{muscle.valve}: Valve check failed, Muscle is already relaxed"
        )
        return False
    valve_actions.turn_valve_off(muscle.valve)
    return True


@device_action(ctx)
def toggle_muscle_state(muscle: MuscleObj) -> bool:
    """
    Toggle a muscle.

    Args:
        muscle (Muscle): the muscle to toggle

    Returns:
        True if the muscle was toggled, False otherwise
    """
    is_contracted = valve_actions.get_valve_state(muscle.valve)
    if is_contracted:
        return relax(muscle)
    return contract(muscle)
