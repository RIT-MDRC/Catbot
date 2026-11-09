"""Hardware-free tests for body-state conversion and error descriptions."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
sys.path.insert(0, str(FOUNDATION_ROOT))

from body_state import (
    flag_messages,
    heartbeat_available,
    kinematic_values,
)
from component.actuator import motion_profile_actions
from component.actuator.actuator import Actuator
from component.actuator.motion_profile import ActuatorMotionProfile, MotionQuantity
from component.can import can_actions
from component.can.can_bus import CanBus
from component.motor import motor_actions
from component.motor.odrive_enums import AxisError


def make_motor(*, inverted=False, **overrides):
    """Create the telemetry attributes used by the state helpers."""
    values = {
        "current_position": 64 / 12,
        "current_velocity": 64 / 24,
        "last_encoder_estimate_time": 9.9,
        "last_heartbeat_time": 9.8,
    }
    values.update(overrides)
    motor = SimpleNamespace(**values)
    name = "state_motor"
    profile_name = "state_profile"
    motor_actions.ctx.store[name] = motor
    motor_actions.ctx.stored_keys.add(name)
    motion_profile_actions.ctx.store[profile_name] = ActuatorMotionProfile(
        motor_turns_per_actuator_turn=64,
        position_min=MotionQuantity(-40, "degrees"),
        position_max=MotionQuantity(40, "degrees"),
        trajectory_velocity=MotionQuantity(1, "motor_turns_per_second"),
        trajectory_acceleration=MotionQuantity(1, "motor_turns_per_second_squared"),
        inverted=inverted,
    )
    motion_profile_actions.ctx.stored_keys.add(profile_name)
    motor.position_min = None
    motor.position_max = None
    return Actuator(motor=name, profile=profile_name)


def test_fresh_kinematics_include_position_and_velocity() -> None:
    valid, position, velocity = kinematic_values(make_motor(), 10.0, 0.25)
    assert valid is True
    assert position == 30.0
    assert velocity == 15.0


def test_inverted_profile_reports_logical_telemetry_direction() -> None:
    valid, position, velocity = kinematic_values(make_motor(inverted=True), 10.0, 0.25)
    assert valid is True
    assert position == -30.0
    assert velocity == -15.0


def test_missing_or_stale_kinematics_are_invalid_nan() -> None:
    for motor in (
        make_motor(current_position=None),
        make_motor(current_velocity=None),
        make_motor(last_encoder_estimate_time=None),
        make_motor(last_encoder_estimate_time=9.0),
    ):
        valid, position, velocity = kinematic_values(motor, 10.0, 0.25)
        assert valid is False
        assert math.isnan(position)
        assert math.isnan(velocity)


def test_heartbeat_freshness() -> None:
    assert heartbeat_available(make_motor(), 10.0, 0.5) is True
    assert heartbeat_available(make_motor(last_heartbeat_time=9.0), 10.0, 0.5) is False
    assert heartbeat_available(make_motor(last_heartbeat_time=None), 10.0, 0.5) is False


def test_flag_messages_describe_multiple_and_unknown_bits() -> None:
    value = int(AxisError.MOTOR_FAILED | AxisError.ENCODER_FAILED) | 0x20
    assert flag_messages(value, AxisError) == [
        "MOTOR_FAILED",
        "ENCODER_FAILED",
        "UNKNOWN_BITS_0x20",
    ]
    assert flag_messages(0, AxisError) == []


def test_can_error_request_uses_remote_frame() -> None:
    bus = object.__new__(CanBus)
    bus.bus = Mock()

    assert can_actions.request_message(bus, 0x23, 8) is True

    message = bus.bus.send.call_args.args[0]
    assert message.arbitration_id == 0x23
    assert message.is_remote_frame is True
    assert message.dlc == 8
