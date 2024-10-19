import cantools
import math
import time
import logging
from enum import IntEnum
from dataclasses import dataclass

from component.can.can_bus import CanBus, send_message, add_listener

from state_management import (
    create_generic_context,
    device,
    device_action,
    device_parser,
)

db = cantools.database.load_file("src/raspi/odrive-cansimple.dbc")

#I can't find documentation of the full enum so I'm just going off of the sample code
class ODriveState(IntEnum):
    IDLE = 1
    FULL_CALIBRATION = 3
    CLOSED_LOOP_CONTROL = 8

@device
@dataclass(slots = True)
class ODriveMotor:
    bus: CanBus
    current_state: int
    current_position: float
    current_velocity: float

    def __init__(self, bus, axisID):
        self.bus = bus
        add_listener(bus, axisID, lambda msg: read_message(self, msg))

def read_message(motor, msg):
    msg_id = msg.arbitration_id & 0x1F
    msg_db = db.get_message_by_frame_id(msg_id)
    match msg_db.name:
        case "Heartbeat": #0x01
            data = msg_db.decode(msg.data)
            motor.current_state = data['Axis_State'].value
        case "Get_Motor_Error": #0x03
            logging.error("Motor Error w/ following data: " + msg_db.decode(msg.data))
        case "Get_Encoder_Error": #0x04
            logging.error("Encoder Error w/ following data: " + msg_db.decode(msg.data))
        case "Get_Sensorless_Error": #0x05
            logging.error("Sensorless Error w/ following data: " + msg_db.decode(msg.data))
        case "Get_Encoder_Estimates": #0x09
            data = msg_db.decode(msg.data)
            motor.current_position = data['Pos_Estimate'].value
            motor.current_velocity = data['Vel_Estimate'].value
            pass
        case "Get_Encoder_Count": #0x0A
            pass
        case "Get_IQ": #0x14
            pass
        case "Get_Sensorless_Estimates": #0x15
            pass
        case "Get_Bus_Voltage_Current": #0x17
            pass
        case "Get_ADC_Voltage": #0x1C
            pass
        case "Get_Controller_Error": #0x1D
            logging.error("Controller Error w/ following data: " + msg_db.decode(msg.data))
        case _:
            logging.warning(f"Unrecognized message \"{msg_db.name}\" recieved (id {hex(msg_id)})")

ctx = create_generic_context("odrive_motor", [ODriveMotor])

@device_parser(ctx)
def parse_odrive(data: dict) -> ODriveMotor:
    return ODriveMotor(**data)

@device_action(ctx)
def set_target_position(motor: ODriveMotor, position: float, velocity: float = 0.0) -> bool:
    msg = db.get_message_by_name("Set_Input_Pos")
    msg_id = msg.frame_id | motor.axisID << 5
    data = msg.encode({'Input_Pos': position, 'Vel_FF': velocity, 'Torque_FF': 0.0})
    return send_message(motor.bus, msg_id, data)

@device_action(ctx)
def set_target_velocity(motor: ODriveMotor, velocity: float) -> bool:
    msg = db.get_message_by_name("Set_Input_Vel")
    msg_id = msg.frame_id | motor.axisID << 5
    data = msg.encode({'Input_Vel': velocity, 'Input_Torque_FF': 0.0})
    return send_message(motor.bus, msg_id, data)

@device_action(ctx)
def get_current_position(motor: ODriveMotor) -> float:
    return motor.current_position

@device_action(ctx)
def get_current_velocity(motor: ODriveMotor) -> float:
    return motor.current_velocity

@device_action(ctx)
def set_limits(motor: ODriveMotor, velocity_limit: float, current_limit: float) -> bool:
    msg = db.get_message_by_name("Set_Limits")
    msg_id = msg.frame_id | motor.axisID << 5
    data = msg.encode({'Velocity_Limit': velocity_limit, 'Current_Limit': current_limit})
    return send_message(motor.bus, msg_id, data)

#TODO: Have this be a recurrent call running in the background rather than needing to call this from the main code
@device_action(ctx)
def update_estimates(motor: ODriveMotor) -> bool:
    msg = db.get_message_by_name("Get_Encoder_Estimates")
    msg_id = msg.frame_id | motor.axisID << 5
    data = msg.encode({'Vel_Estimate': 0.0, 'Pos_Estimate': 0.0})
    return send_message(motor.bus, msg_id, data)    

@device_action(ctx)
def set_state(motor: ODriveMotor, state: int) -> bool:
    msg = db.get_message_by_name("Set_Axis_State")
    msg_id = msg.frame_id | motor.axisID << 5
    data = msg.encode({'Axis_Requested_State': state})
    return send_message(motor.bus, msg_id, data)

@device_action(ctx)
def get_state(motor: ODriveMotor) -> int:
    return motor.current_state
