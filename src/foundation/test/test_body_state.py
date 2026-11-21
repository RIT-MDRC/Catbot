"""Hardware-free tests for body-state conversion and error descriptions."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
sys.path.insert(0, str(FOUNDATION_ROOT))

from body_state import (
    flag_messages,
    heartbeat_available,
    kinematic_values,
)
from component.actuator import actuator_actions, motion_profile_actions
from component.actuator.actuator import Actuator
from component.actuator.motion_profile import (
    ActuatorMotionProfile,
    BallscrewLinkage,
    MotionQuantity,
)
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


def test_kinematics_use_supplied_snapshot_without_rereading_live_state(monkeypatch):
    actuator = make_motor()
    snapshot = motor_actions.get_state_snapshot(actuator.motor)
    reader = Mock(side_effect=AssertionError("Must reuse the captured motor state"))
    monkeypatch.setattr(motor_actions, "get_state_snapshot", reader)
    assert kinematic_values(actuator, 10.0, 0.25, motor_state=snapshot) == (
        True,
        30.0,
        15.0,
    )
    reader.assert_not_called()


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
        make_motor(last_encoder_estimate_time=11.0),
        make_motor(current_position=math.nan),
        make_motor(current_velocity=math.inf),
    ):
        valid, position, velocity = kinematic_values(motor, 10.0, 0.25)
        assert valid is False
        assert math.isnan(position)
        assert math.isnan(velocity)


def test_unreachable_knee_feedback_is_invalid_and_recovers_on_reachable_sample():
    actuator = make_motor(current_position=21.353660583496094, current_velocity=0.0)
    profile = ActuatorMotionProfile(
        motor_turns_per_actuator_turn=None,
        inverted=True,
        position_min=MotionQuantity(-55, "degrees"),
        position_max=MotionQuantity(55, "degrees"),
        trajectory_velocity=MotionQuantity(1, "motor_turns_per_second"),
        trajectory_acceleration=MotionQuantity(1, "motor_turns_per_second_squared"),
        ballscrew_linkage=BallscrewLinkage(
            L1=7.235,
            L2=18.6452,
            A=11.869,
            B=7.95,
            ballscrew_travel_per_motor_turn=MotionQuantity(5, "millimeters"),
            x_offset=MotionQuantity(6.76, "centimeters"),
        ),
    )
    motion_profile_actions.ctx.store["state_profile"] = profile
    valid, position, velocity = kinematic_values(actuator, 10.0, 0.25)
    assert not valid and math.isnan(position) and math.isnan(velocity)
    motor_actions.ctx.store[
        "state_motor"
    ].current_position = actuator_actions.position_to_motor_turns(actuator, 0)
    valid, position, velocity = kinematic_values(actuator, 10.0, 0.25)
    assert valid and position == pytest.approx(0, abs=1e-8)
    assert velocity == pytest.approx(0)


@pytest.mark.parametrize(
    "action", ["motor_turns_to_position", "motor_turns_to_velocity"]
)
def test_conversion_errors_and_nonfinite_results_are_invalid(monkeypatch, action):
    actuator = make_motor()
    convert = Mock(side_effect=ValueError("conversion failed"))
    monkeypatch.setattr(actuator_actions, action, convert)
    valid, position, velocity = kinematic_values(actuator, 10.0, 0.25)
    assert not valid and math.isnan(position) and math.isnan(velocity)
    convert.side_effect = None
    convert.return_value = math.inf
    valid, position, velocity = kinematic_values(actuator, 10.0, 0.25)
    assert not valid and math.isnan(position) and math.isnan(velocity)


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
