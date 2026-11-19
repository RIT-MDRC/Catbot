"""Controlled mapping inputs, independent of the robot's calibration."""

import json


def mapping_values():
    return {
        "actuator_names": [f"joint_{i}" for i in range(12)],
        "signs": [1] * 12,
        "offsets_degrees": [0, 0, 90] * 4,
        "minimum_degrees": [-40, -40, -55] * 4,
        "maximum_degrees": [40, 40, 55] * 4,
    }


def write_mapping(root):
    path = root / "mapping.json"
    path.write_text(json.dumps(mapping_values()))
    return path
