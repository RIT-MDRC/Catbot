import logging
import os
from dataclasses import dataclass

import cantools

from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from ..can import can_actions
from .odrive_enums import *

ODRIVE_CAN_DB = cantools.db.load_file(
    os.path.dirname(__file__) + "/odrive-cansimple.dbc"
)


@device
@dataclass
class ODriveMotor:
    axisID: int
    control_mode: ControlMode
    input_mode: InputMode
    # reminder: fields with default values must come after fields without defaults
    bus: can_actions.CanBus = identifier(can_actions.ctx)
    position_min: float = None
    position_max: float = None

    current_state: MotorState = MotorState.UNDEFINED
    current_position: float = None
    current_velocity: float = None

    strict_bounds: bool = True

    def __post_init__(self):
        can_actions.add_listener(
            self.bus, self.axisID, lambda msg: read_message(self, msg)
        )


# region Message Handling

EVENT_HANDLE = dict()
EVENT_IGNORE = [
    "Get_Encoder_Count",
    "Get_IQ",
    "Get_Sensorless_Estimates",
    "Get_Bus_Voltage_Current",
    "Get_ADC_Voltage",
]


def read_message(motor: ODriveMotor, msg):
    msg_id = msg.arbitration_id & 0x1F
    msg_db = ODRIVE_CAN_DB.get_message_by_frame_id(msg_id)
    if msg_db.name in EVENT_HANDLE:
        EVENT_HANDLE[msg_db.name](motor, msg_db.decode(msg.data))
    elif msg_db.name not in EVENT_IGNORE:
        logging.warning(
            f'Unrecognized message "{msg_db.name}" recieved (id {hex(msg_id)})'
        )


def event_decorator(name):
    def wrapper(func):
        EVENT_HANDLE[name] = func
        return func

    return wrapper


@event_decorator("Heartbeat")
def read_heartbeat(motor: ODriveMotor, data):
    state = data["Axis_State"].value
    if motor.current_state != state:
        motor.current_state = state
        logging.info(f"Axis {motor.axisID} Heartbeat w/ state: " + str(state) + " data: " + f"{data}")
        axis_error = data["Axis_Error"]
        if get_error_num(axis_error) != 0:
            logging.error(
                f"Axis {motor.axisID} Error w/ following data: " + str(axis_error)
            )


@event_decorator("Get_Encoder_Estimates")
def update_estimates(motor: ODriveMotor, data):
    logging.info(f"Axis {motor.axisID} Encoder Estimates {data}")
    motor.current_position = data["Pos_Estimate"]
    motor.current_velocity = data["Vel_Estimate"]

    if motor.strict_bounds:
        if (
            motor.position_min is not None
            and motor.current_position <= motor.position_min
            and motor.current_velocity < 0
        ):
            logging.warning(f"Motor {motor.axisID} has reached its lower bounds.")
            stop(motor)
        elif (
            motor.position_max is not None
            and motor.current_position >= motor.position_max
            and motor.current_velocity > 0
        ):
            logging.warning(f"Motor {motor.axisID} has reached its upper bounds.")
            stop(motor)


@event_decorator("Get_Motor_Error")
def report_motor_error(motor: ODriveMotor, data):
    logging.error(f"Motor Error on axis {motor.axisID} w/ following data: " + str(data))


@event_decorator("Get_Encoder_Error")
def report_encoder_error(motor: ODriveMotor, data):
    logging.error(
        f"Encoder Error on axis {motor.axisID} w/ following data: " + str(data)
    )


@event_decorator("Get_Sensorless_Error")
def report_sensorless_error(motor: ODriveMotor, data):
    logging.error(
        f"Sensorless Error on axis {motor.axisID} w/ following data: " + str(data)
    )


@event_decorator("Get_Controller_Error")
def report_controller_error(motor: ODriveMotor, data):
    logging.error(
        f"Controller Error on axis {motor.axisID} w/ following data: " + str(data)
    )


def get_error_num(error):
    # errors are flags, which cantools does not properly handle
    # if only 1 flag is present, it returns a "NamedSignalValue"
    # if multiple flags are present, it returns an int
    # "NamedSignalValue" can not be cast to int, the only way to get the number is to do "error.value", which is invalid if "error" is an int
    if isinstance(error, int):
        return error
    else:
        return error.value


# endregion

# region Device Actions

ctx = create_generic_context("odrive_motor", [ODriveMotor])


@device_parser(ctx)
def parse_odrive(data: dict) -> ODriveMotor:
    return ODriveMotor(**data)


@device_action(ctx)
def set_target_position(
    motor: ODriveMotor,
    position: float,
    velocity_FF: float = 0.0,
    torque_FF: float = 0.0,
) -> bool:
    """Set the target position for this motor
    Only use this function if Control Mode is set to POSITION_CONTROL"""
    if motor.control_mode != ControlMode.POSITION_CONTROL:
        logging.error(
            f"Can not set position on motor {motor.axisID} when not set to POSITION_CONTROL."
        )
        return False
    if motor.position_min != None and position < motor.position_min:
        if motor.strict_bounds:
            logging.error(
                f"Attempting to set position on motor {motor.axisID} past lower bounds in strict bounds mode. This can be turned off by setting strict_bounds to False in pinconfig.json."
            )
            return False
        logging.warning(
            f"Attempting to set position on motor {motor.axisID} past lower bounds."
        )
        position = motor.position_min
    elif motor.position_max != None and position > motor.position_max:
        if motor.strict_bounds:
            logging.error(
                f"Attempting to set position on motor {motor.axisID} past upper bounds in strict bounds mode. This can be turned off by setting strict_bounds to False in pinconfig.json."
            )
            return False
        logging.warning(
            f"Attempting to set position on motor {motor.axisID} past upper bounds."
        )
        position = motor.position_max
    return send_message(
        motor,
        "Set_Input_Pos",
        {"Input_Pos": position, "Vel_FF": velocity_FF, "Torque_FF": torque_FF},
    )


@device_action(ctx)
def set_trajectory_velocity(motor: ODriveMotor, velocity: float) -> bool:
    return send_message(motor, "Set_Traj_Vel_Limit", {"Traj_Vel_Limit": velocity})


@device_action(ctx)
def set_trajectory_accel(motor: ODriveMotor, accel: float, decel: float = None) -> bool:
    return send_message(
        motor,
        "Set_Traj_Accel_Limits",
        {"Traj_Accel_Limit": accel, "Traj_Decel_Limit": decel if decel else accel},
    )


@device_action(ctx)
def set_target_velocity(
    motor: ODriveMotor, velocity: float, torque_FF: float = 0.0
) -> bool:
    """Set the target velocity for this motor"""
    if (
        motor.control_mode == ControlMode.POSITION_CONTROL
        and motor.input_mode == InputMode.TRAP_TRAJ
    ):
        return set_trajectory_velocity(motor, velocity)
    elif motor.control_mode != ControlMode.VELOCITY_CONTROL:
        logging.error(
            f"Can not set input velocity on motor {motor.axisID} when not set to VELOCITY_CONTROL."
        )
        return False
    return send_message(
        motor, "Set_Input_Vel", {"Input_Vel": velocity, "Input_Torque_FF": torque_FF}
    )


@device_action(ctx)
def stop(motor: ODriveMotor):
    match motor.control_mode:
        case ControlMode.POSITION_CONTROL:
            if motor.current_position is not None:
                set_target_position(motor, motor.current_position)
        case ControlMode.VELOCITY_CONTROL:
            set_target_velocity(motor, 0)


@device_action(ctx)
def get_current_position(motor: ODriveMotor) -> float:
    return motor.current_position


@device_action(ctx)
def get_position_limits(motor: ODriveMotor) -> list[float]:
    return [motor.position_min, motor.position_max]


@device_action(ctx)
def get_current_velocity(motor: ODriveMotor) -> float:
    return motor.current_velocity


## These are safety limits set by the hardware team. DO NOT CHANGE THESE LIMITS.
# @device_action(ctx)
# def set_limits(motor: ODriveMotor, velocity_limit: float, current_limit: float) -> bool:
#     """Set the velocity and current limits for this motor
#     Consider changing the motor's config instead of using this function"""
#     return send_message(motor, "Set_Limits", {'Velocity_Limit': velocity_limit, 'Current_Limit': current_limit})


@device_action(ctx)
def request_set_state(motor: ODriveMotor, state: MotorState) -> bool:
    """Set the state of the motor
    Motor will not recieve position/velocity input if not set to CLOSED_LOOP_CONTROL"""
    return send_message(motor, "Set_Axis_State", {"Axis_Requested_State": state})


@device_action(ctx)
def get_state(motor: ODriveMotor) -> MotorState:
    """Returns the most recent state reported by the motor."""
    return motor.current_state


@device_action(ctx)
def set_controller_mode(
    motor: ODriveMotor,
    new_control_mode: ControlMode = None,
    new_input_mode: InputMode = None,
) -> bool:
    if new_control_mode != ControlMode.POSITION_CONTROL and (
        motor.position_min is not None or motor.position_max is not None
    ):
        logging.warning(
            f"Motor {motor.axisID} has position limits, but is being set to non-position control. Position limits can not be enforced under non-position control."
        )
    res = send_message(
        motor,
        "Set_Controller_Mode",
        {
            "Control_Mode": (
                new_control_mode if new_control_mode else motor.control_mode
            ),
            "Input_Mode": new_input_mode if new_input_mode else motor.input_mode,
        },
    )
    if res:
        motor.control_mode = new_control_mode
        motor.input_mode = new_input_mode


@device_action(ctx)
def clear_error_message(motor: ODriveMotor):
    return send_message(motor, "Clear_Errors", {})


@device_action(ctx)
def get_control_mode(motor: ODriveMotor) -> ControlMode:
    return motor.control_mode


@device_action(ctx)
def get_input_mode(motor: ODriveMotor) -> InputMode:
    return motor.input_mode


@device_action(ctx)
def send_message(motor: ODriveMotor, msg_name: str, data: dict) -> bool:
    msg = ODRIVE_CAN_DB.get_message_by_name(msg_name)
    msg_id = msg.frame_id | motor.axisID << 5
    data = msg.encode(data)
    return can_actions.send_message(motor.bus, msg_id, data)


# endregion
