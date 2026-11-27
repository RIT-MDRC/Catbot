"""Shared firmware protocol data, without GPIO/CAN initialization."""

import json
import os
from enum import IntEnum
from pathlib import Path


def load_protocol(path):
    data = json.loads(Path(path).read_text())
    for group in ("MotorState", "ControlMode", "InputMode"):
        values = list(data[group].values())
        if (
            not values
            or any(type(value) is not int or not 0 <= value <= 255 for value in values)
            or len(values) != len(set(values))
        ):
            raise ValueError(f"Invalid or duplicate protocol values in {group}")
    bits = data["can_command_bits"]
    heartbeat = data["heartbeat_command"]
    if (
        type(bits) is not int
        or not 1 <= bits <= 10
        or type(heartbeat) is not int
        or not 0 <= heartbeat < 1 << bits
    ):
        raise ValueError("Invalid CAN command layout")
    dbc = Path(data["dbc_file"]).expanduser()
    data["dbc_file"] = str(
        dbc if dbc.is_absolute() else Path(path).resolve().parent / dbc
    )
    if not Path(data["dbc_file"]).is_file():
        raise ValueError("Configured CAN DBC does not exist")
    return data


PROTOCOL_FILE = Path(
    os.environ.get("CATBOT_PROTOCOL_CONFIG")
    or Path(__file__).with_name("hardware_protocol.json")
).expanduser()
PROTOCOL = load_protocol(PROTOCOL_FILE)
COMMAND_BITS = PROTOCOL["can_command_bits"]
COMMAND_MASK = (1 << COMMAND_BITS) - 1
HEARTBEAT_COMMAND = PROTOCOL["heartbeat_command"]
DBC_FILE = PROTOCOL["dbc_file"]


class MotorState(IntEnum):
    UNDEFINED = PROTOCOL["MotorState"]["UNDEFINED"]
    IDLE = PROTOCOL["MotorState"]["IDLE"]
    STARTUP_SEQUENCE = PROTOCOL["MotorState"]["STARTUP_SEQUENCE"]
    FULL_CALIBRATION_SEQUENCE = PROTOCOL["MotorState"]["FULL_CALIBRATION_SEQUENCE"]
    MOTOR_CALIBRATION = PROTOCOL["MotorState"]["MOTOR_CALIBRATION"]
    ENCODER_INDEX_SEARCH = PROTOCOL["MotorState"]["ENCODER_INDEX_SEARCH"]
    ENCODER_OFFSET_CALIBRATION = PROTOCOL["MotorState"]["ENCODER_OFFSET_CALIBRATION"]
    CLOSED_LOOP_CONTROL = PROTOCOL["MotorState"]["CLOSED_LOOP_CONTROL"]
    LOCKIN_SPIN = PROTOCOL["MotorState"]["LOCKIN_SPIN"]
    ENCODER_DIR_FIND = PROTOCOL["MotorState"]["ENCODER_DIR_FIND"]
    HOMING = PROTOCOL["MotorState"]["HOMING"]
    ENCODER_HALL_POLARITY_CALIBRATION = PROTOCOL["MotorState"][
        "ENCODER_HALL_POLARITY_CALIBRATION"
    ]
    ENCODER_HALL_PHASE_CALIBRATION = PROTOCOL["MotorState"][
        "ENCODER_HALL_PHASE_CALIBRATION"
    ]


class InputMode(IntEnum):
    INACTIVE = PROTOCOL["InputMode"]["INACTIVE"]
    PASSTHROUGH = PROTOCOL["InputMode"]["PASSTHROUGH"]
    VEL_RAMP = PROTOCOL["InputMode"]["VEL_RAMP"]
    POS_FILTER = PROTOCOL["InputMode"]["POS_FILTER"]
    MIX_CHANNELS = PROTOCOL["InputMode"]["MIX_CHANNELS"]
    TRAP_TRAJ = PROTOCOL["InputMode"]["TRAP_TRAJ"]
    TORQUE_RAMP = PROTOCOL["InputMode"]["TORQUE_RAMP"]
    MIRROR = PROTOCOL["InputMode"]["MIRROR"]
    TUNING = PROTOCOL["InputMode"]["TUNING"]


class ControlMode(IntEnum):
    VOLTAGE_CONTROL = PROTOCOL["ControlMode"]["VOLTAGE_CONTROL"]
    TORQUE_CONTROL = PROTOCOL["ControlMode"]["TORQUE_CONTROL"]
    VELOCITY_CONTROL = PROTOCOL["ControlMode"]["VELOCITY_CONTROL"]
    POSITION_CONTROL = PROTOCOL["ControlMode"]["POSITION_CONTROL"]
