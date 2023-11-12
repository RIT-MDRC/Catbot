import json
from control.muscle import *
from io.pneumatics import add_valve_pin

from util import *


def setup():
    data = get_pinconfig()
    set_pin(data)


def get_pinconfig(filepath: str = "src/pinconfig.json") -> dict:
    """
    Get the pin configuration from a JSON file.

    :param filepath: the path to the JSON file
    :return: the pin configuration
    """
    with open(filepath, "r") as file:
        return json.load(file)


def set_pin(config_data: dict) -> dict:
    """
    Set the pin configuration.

    Args:
        config_data (dict): the pin configuration

    """
    ret = {}
    keys = config_data.keys()
    for key in keys:
        if str.endswith(key, "valve"):
            pin = config_data[key]
            od = create_valve_device(pin)
            add_valve_pin(key, od)
            ret[key] = od
        elif str.endswith(key, "pressure"):
            pin = config_data[key]
            id = create_pressure_device(pin)
            add_valve_pin(key, id)
            ret[key] = id
        elif str.endswith(key, "muscle"):
            raw_muscle = set_pin(config_data[key])
            muscle = create_dataclass(MuscleObj(), raw_muscle)
            add_muscle(key, muscle)
            ret[key] = muscle
        else:
            raise ValueError(f"Invalid key {key}")
