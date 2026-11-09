import logging
import os
import time
from dataclasses import dataclass
from typing import cast

import cantools
from cantools.database.can import Database
from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from ..can import can_actions
from .odrive_enums import AxisError, ControlMode, InputMode, MotorState

logger = logging.getLogger(__name__)
ODRIVE_CAN_DB = cast(
    Database,
    cantools.database.load_file(
        os.path.dirname(__file__) + "/odrive-cansimple.dbc"
    ),
)


@device
@dataclass
class ODriveMotor:
    axisID: int
    control_mode: ControlMode
    input_mode: InputMode
    bus: can_actions.CanBus = identifier(can_actions.ctx)  # noqa: RUF009
    position_min: float | None = None
    position_max: float | None = None

    current_state: MotorState = MotorState.UNDEFINED
    axis_error: int = 0
    current_position: float | None = None
    current_velocity: float | None = None
    last_heartbeat_time: float | None = None
    last_encoder_estimate_time: float | None = None

    motor_error: int = 0
    encoder_error: int = 0
    sensorless_error: int = 0
    controller_error: int = 0
    motor_error_flag: bool = False
    encoder_error_flag: bool = False
    sensorless_error_flag: bool = False
    controller_error_flag: bool = False

    strict_bounds: bool = True

    def __post_init__(self):
        can_actions.add_listener(
            self.bus, self.axisID, lambda msg: read_message(self, msg)
        )


@dataclass(frozen=True)
class ODriveMotorState:
    """Read-only snapshot of state exposed to framework consumers."""

    axis_id: int
    current_state: MotorState
    axis_error: int
    current_position: float | None
    current_velocity: float | None
    last_heartbeat_time: float | None
    last_encoder_estimate_time: float | None
    motor_error: int
    encoder_error: int
    sensorless_error: int
    controller_error: int
    motor_error_flag: bool
    encoder_error_flag: bool
    sensorless_error_flag: bool
    controller_error_flag: bool

    @property
    def axisID(self) -> int:
        """Preserve the configured ODrive axis field spelling for consumers."""
        return self.axis_id


# region Message Handling

EVENT_HANDLE = {}
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
        logger.warning(
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
    axis_error = data["Axis_Error"]
    motor.last_heartbeat_time = time.monotonic()
    motor.axis_error = get_error_num(axis_error)
    motor.motor_error_flag = bool(data["Motor_Error_Flag"])
    motor.encoder_error_flag = bool(data["Encoder_Error_Flag"])
    motor.controller_error_flag = bool(data["Controller_Error_Flag"])
    motor.sensorless_error_flag = bool(
        motor.axis_error & AxisError.SENSORLESS_ESTIMATOR_FAILED
    )
    if motor.current_state != state:
        motor.current_state = state
        logger.info(
            f"Axis {motor.axisID} Heartbeat w/ state: "
            + str(state)
            + " data: "
            + f"{data}"
        )
        if motor.axis_error != 0:
            logger.error(
                f"Axis {motor.axisID} Error w/ following data: " + str(axis_error)
            )


@event_decorator("Get_Encoder_Estimates")
def update_estimates(motor: ODriveMotor, data):
    posEstimate = data["Pos_Estimate"]
    velEstimate = data["Vel_Estimate"]
    if motor.current_position != posEstimate or motor.current_velocity != velEstimate:
        logger.info(f"New Axis {motor.axisID} Encoder Estimates {data}")
    motor.current_position = posEstimate
    motor.current_velocity = velEstimate
    motor.last_encoder_estimate_time = time.monotonic()

    position = motor.current_position
    velocity = motor.current_velocity
    if motor.strict_bounds and position is not None and velocity is not None:
        if (
            motor.position_min is not None
            and position <= motor.position_min
            and velocity < 0
        ):
            logger.warning(f"Motor {motor.axisID} has reached its lower bounds.")
            stop(motor)
        elif (
            motor.position_max is not None
            and position >= motor.position_max
            and velocity > 0
        ):
            logger.warning(f"Motor {motor.axisID} has reached its upper bounds.")
            stop(motor)


@event_decorator("Get_Motor_Error")
def report_motor_error(motor: ODriveMotor, data):
    motor.motor_error = get_error_num(data["Motor_Error"])
    if motor.motor_error:
        logger.error(
            f"Motor Error on axis {motor.axisID} w/ following data: " + str(data)
        )


@event_decorator("Get_Encoder_Error")
def report_encoder_error(motor: ODriveMotor, data):
    motor.encoder_error = get_error_num(data["Encoder_Error"])
    if motor.encoder_error:
        logger.error(
            f"Encoder Error on axis {motor.axisID} w/ following data: " + str(data)
        )


@event_decorator("Get_Sensorless_Error")
def report_sensorless_error(motor: ODriveMotor, data):
    motor.sensorless_error = get_error_num(data["Sensorless_Error"])
    if motor.sensorless_error:
        logger.error(
            f"Sensorless Error on axis {motor.axisID} w/ following data: " + str(data)
        )


@event_decorator("Get_Controller_Error")
def report_controller_error(motor: ODriveMotor, data):
    motor.controller_error = get_error_num(data["Controller_Error"])
    if motor.controller_error:
        logger.error(
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


def get_names() -> tuple[str, ...]:
    """Return configured motor component names."""
    return tuple(ctx.store)


@device_action(ctx)
def get_state_snapshot(motor: ODriveMotor) -> ODriveMotorState:
    """Return a stable read-only snapshot of one motor's observable state."""
    return ODriveMotorState(
        axis_id=getattr(motor, "axisID", 0),
        current_state=getattr(motor, "current_state", MotorState.UNDEFINED),
        axis_error=getattr(motor, "axis_error", 0),
        current_position=getattr(motor, "current_position", None),
        current_velocity=getattr(motor, "current_velocity", None),
        last_heartbeat_time=getattr(motor, "last_heartbeat_time", None),
        last_encoder_estimate_time=getattr(
            motor, "last_encoder_estimate_time", None
        ),
        motor_error=getattr(motor, "motor_error", 0),
        encoder_error=getattr(motor, "encoder_error", 0),
        sensorless_error=getattr(motor, "sensorless_error", 0),
        controller_error=getattr(motor, "controller_error", 0),
        motor_error_flag=getattr(motor, "motor_error_flag", False),
        encoder_error_flag=getattr(motor, "encoder_error_flag", False),
        sensorless_error_flag=getattr(motor, "sensorless_error_flag", False),
        controller_error_flag=getattr(motor, "controller_error_flag", False),
    )


@device_action(ctx)
def set_position_bounds(
    motor: ODriveMotor, minimum: float, maximum: float
) -> None:
    """Set validated raw position bounds for an actuator-owned motor."""
    if motor.position_min is not None or motor.position_max is not None:
        raise ValueError(
            "actuator-referenced ODrive motors may not define raw position bounds"
        )
    motor.position_min, motor.position_max = sorted((minimum, maximum))


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
        logger.error(
            f"Can not set position on motor {motor.axisID} when not set to POSITION_CONTROL."
        )
        return False
    if motor.position_min is not None and position < motor.position_min:
        if motor.strict_bounds:
            logger.error(
                f"Attempting to set position on motor {motor.axisID} past lower bounds in strict bounds mode. This can be turned off by setting strict_bounds to False in pinconfig.json."
            )
            return False
        logger.warning(
            f"Attempting to set position on motor {motor.axisID} past lower bounds."
        )
        position = motor.position_min
    elif motor.position_max is not None and position > motor.position_max:
        if motor.strict_bounds:
            logger.error(
                f"Attempting to set position on motor {motor.axisID} past upper bounds in strict bounds mode. This can be turned off by setting strict_bounds to False in pinconfig.json."
            )
            return False
        logger.warning(
            f"Attempting to set position on motor {motor.axisID} past upper bounds."
        )
        position = motor.position_max
    return send_message(
        motor,
        "Set_Input_Pos",
        {"Input_Pos": position, "Vel_FF": velocity_FF, "Torque_FF": torque_FF},
    )


@device_action(ctx)
def set_position_control_velocity(
    motor: ODriveMotor,
    velocity_FF: float = 0.0,
) -> bool:
    logger.info("Setting position control velocity")
    return send_message(
        motor,
        "Set_Input_Pos",
        {
            "Input_Pos": ControlMode.POSITION_CONTROL,
            "Vel_FF": velocity_FF,
            "Torque_FF": 0.0,
        },
    )


@device_action(ctx)
def set_trajectory_velocity(motor: ODriveMotor, velocity: float) -> bool:
    logger.info("Setting trajectory velocity")
    return send_message(motor, "Set_Traj_Vel_Limit", {"Traj_Vel_Limit": velocity})


@device_action(ctx)
def set_trajectory_accel(
    motor: ODriveMotor, accel: float, decel: float | None = None
) -> bool:
    logger.info("Setting trajectory acceleration")
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
    logger.info(f"Setting target velocity to {velocity}")
    if (
        motor.control_mode == ControlMode.POSITION_CONTROL
        and motor.input_mode == InputMode.TRAP_TRAJ
    ):
        return set_trajectory_velocity(motor, velocity)
    elif motor.control_mode != ControlMode.VELOCITY_CONTROL:
        logger.error(
            f"Can not set input velocity on motor {motor.axisID} when not set to VELOCITY_CONTROL."
        )
        return False
    return send_message(
        motor, "Set_Input_Vel", {"Input_Vel": velocity, "Input_Torque_FF": torque_FF}
    )


@device_action(ctx)
def stop(motor: ODriveMotor):
    logger.info(f"Stopping motor(Axis: {motor.axisID})")
    match motor.control_mode:
        case ControlMode.POSITION_CONTROL:
            if motor.current_position is not None:
                set_target_position(motor, motor.current_position)
        case ControlMode.VELOCITY_CONTROL:
            set_target_velocity(motor, 0)


@device_action(ctx)
def get_current_position(motor: ODriveMotor) -> float | None:
    logger.info(f"Getting current position of motor(Axis: {motor.axisID})")
    return motor.current_position


@device_action(ctx)
def get_position_limits(motor: ODriveMotor) -> list[float | None]:
    logger.info(f"Getting position limits of motor(Axis: {motor.axisID})")
    return [motor.position_min, motor.position_max]


@device_action(ctx)
def get_current_velocity(motor: ODriveMotor) -> float | None:
    logger.info(f"Getting current velocity of motor(Axis: {motor.axisID})")
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
    logger.info(f"Setting state of motor(Axis: {motor.axisID}) to {state}")
    return send_message(motor, "Set_Axis_State", {"Axis_Requested_State": state})


@device_action(ctx)
def get_state(motor: ODriveMotor) -> MotorState:
    """Returns the most recent state reported by the motor."""
    logger.info(f"Getting state of motor(Axis: {motor.axisID})")
    return motor.current_state


@device_action(ctx)
def set_controller_mode(
    motor: ODriveMotor,
    new_control_mode: ControlMode | None = None,
    new_input_mode: InputMode | None = None,
) -> bool:
    control_mode = motor.control_mode if new_control_mode is None else new_control_mode
    input_mode = motor.input_mode if new_input_mode is None else new_input_mode
    if control_mode != ControlMode.POSITION_CONTROL and (
        motor.position_min is not None or motor.position_max is not None
    ):
        logger.warning(
            f"Motor {motor.axisID} has position limits, but is being set to non-position control. Position limits can not be enforced under non-position control."
        )
    res = send_message(
        motor,
        "Set_Controller_Mode",
        {
            "Control_Mode": control_mode,
            "Input_Mode": input_mode,
        },
    )
    if res:
        motor.control_mode = control_mode
        motor.input_mode = input_mode
    return res


@device_action(ctx)
def clear_error_message(motor: ODriveMotor):
    result = send_message(motor, "Clear_Errors", {})
    if result:
        motor.motor_error = 0
        motor.encoder_error = 0
        motor.sensorless_error = 0
        motor.controller_error = 0
    return result


@device_action(ctx)
def request_error_details(motor: ODriveMotor) -> bool:
    """Request detailed CANSimple 0.5.6 errors indicated by the heartbeat."""
    message_names = []
    if motor.motor_error_flag:
        message_names.append("Get_Motor_Error")
    if motor.encoder_error_flag:
        message_names.append("Get_Encoder_Error")
    if motor.sensorless_error_flag:
        message_names.append("Get_Sensorless_Error")
    if motor.controller_error_flag:
        message_names.append("Get_Controller_Error")
    result = True
    for name in message_names:
        result = request_message(motor, name) and result
    return result


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
    encoded_data = msg.encode(data)
    return can_actions.send_message(motor.bus, msg_id, encoded_data)


@device_action(ctx)
def request_message(motor: ODriveMotor, msg_name: str) -> bool:
    msg = ODRIVE_CAN_DB.get_message_by_name(msg_name)
    msg_id = msg.frame_id | motor.axisID << 5
    return can_actions.request_message(motor.bus, msg_id, msg.length)


@device_action(ctx)
def reboot(motor: ODriveMotor) -> bool:
    return send_message(motor, "Reboot", {})


@device_action(ctx)
def set_axis_state(motor: ODriveMotor, state: MotorState) -> bool:
    logger.info(f"Motor {motor.axisID} is being set to state {state}")
    return send_message(motor, "Set_Axis_State", {"Axis_Requested_State": state})


# endregion
