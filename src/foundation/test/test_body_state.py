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
    motor_turns_to_degrees,
)
from component.can import can_actions
from component.can.can_bus import CanBus
from component.motor.odrive_enums import AxisError


def make_motor(**overrides):
    """Create the telemetry attributes used by the state helpers."""
    values = {
        "current_position": 64 / 12,
        "current_velocity": 64 / 24,
        "last_encoder_estimate_time": 9.9,
        "last_heartbeat_time": 9.8,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_motor_turns_convert_back_to_joint_degrees() -> None:
    assert motor_turns_to_degrees(64 / 12) == 30.0
    assert motor_turns_to_degrees(-64 / 24) == -15.0


def test_fresh_kinematics_include_position_and_velocity() -> None:
    valid, position, velocity = kinematic_values(make_motor(), 10.0, 0.25)
    assert valid is True
    assert position == 30.0
    assert velocity == 15.0


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
