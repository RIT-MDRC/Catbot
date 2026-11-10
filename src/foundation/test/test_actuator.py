"""Hardware-free tests for actuator profiles and motor-boundary behavior."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
sys.path.insert(0, str(FOUNDATION_ROOT))

from component.actuator import actuator_actions, motion_profile_actions
from component.actuator.actuator import Actuator
from component.actuator.motion_profile import (
    ActuatorMotionProfile,
    BallscrewLinkage,
    MotionQuantity,
)
from component.motor import motor_actions
from component.motor.odrive_enums import ControlMode, InputMode


def quantity(value, unit):
    return MotionQuantity(value, unit)


def profile(*, inverted=False, minimum=-40, maximum=40):
    return ActuatorMotionProfile(
        motor_turns_per_actuator_turn=64,
        inverted=inverted,
        position_min=quantity(minimum, "degrees"),
        position_max=quantity(maximum, "degrees"),
        trajectory_velocity=quantity(1, "motor_turns_per_second"),
        trajectory_acceleration=quantity(1, "motor_turns_per_second_squared"),
    )


def make_actuator(name, *, inverted=False, minimum=-40, maximum=40):
    motor = SimpleNamespace(
        axisID=0,
        control_mode=ControlMode.POSITION_CONTROL,
        input_mode=InputMode.TRAP_TRAJ,
        position_min=None,
        position_max=None,
        current_position=None,
        current_velocity=None,
    )
    profile_name = f"{name}_profile"
    motor_actions.ctx.store[name] = motor
    motor_actions.ctx.stored_keys.add(name)
    motion_profile_actions.ctx.store[profile_name] = profile(
        inverted=inverted, minimum=minimum, maximum=maximum
    )
    motion_profile_actions.ctx.stored_keys.add(profile_name)
    actuator = Actuator(motor=name, profile=profile_name)
    actuator_actions.ctx.store[name] = actuator
    actuator_actions.ctx.stored_keys.add(name)
    return actuator, motor


def make_knee_actuator(name="knee", *, x_offset=0.0):
    motor = SimpleNamespace(
        axisID=4,
        control_mode=ControlMode.POSITION_CONTROL,
        input_mode=InputMode.TRAP_TRAJ,
        position_min=None,
        position_max=None,
        current_position=None,
        current_velocity=None,
    )
    linkage = BallscrewLinkage(
        L1=7.235,
        L2=18.6452,
        A=11.869,
        B=7.95,
        ballscrew_travel_per_motor_turn=quantity(10, "millimeters"),
        x_offset=quantity(x_offset, "centimeters"),
    )
    knee_profile = ActuatorMotionProfile(
        motor_turns_per_actuator_turn=None,
        position_min=quantity(-55, "degrees"),
        position_max=quantity(55, "degrees"),
        trajectory_velocity=quantity(1, "motor_turns_per_second"),
        trajectory_acceleration=quantity(1, "motor_turns_per_second_squared"),
        ballscrew_linkage=linkage,
    )
    motor_actions.ctx.store[name] = motor
    motor_actions.ctx.stored_keys.add(name)
    motion_profile_actions.ctx.store["knee_profile"] = knee_profile
    motion_profile_actions.ctx.stored_keys.add("knee_profile")
    actuator = Actuator(motor=name, profile="knee_profile")
    return actuator, motor


@pytest.fixture(autouse=True)
def clear_component_stores():
    contexts = (
        actuator_actions.ctx,
        motion_profile_actions.ctx,
        motor_actions.ctx,
    )
    snapshots = [(dict(ctx.store), set(ctx.stored_keys)) for ctx in contexts]
    for ctx in contexts:
        ctx.store.clear()
        ctx.stored_keys.clear()
    yield
    for ctx, (store, keys) in zip(contexts, snapshots):
        ctx.store.clear()
        ctx.store.update(store)
        ctx.stored_keys.clear()
        ctx.stored_keys.update(keys)


@pytest.mark.parametrize("inverted,direction", [(False, 1), (True, -1)])
def test_bidirectional_position_and_velocity_conversion(inverted, direction):
    actuator, _ = make_actuator("joint", inverted=inverted)

    assert actuator_actions.position_to_motor_turns(actuator, 30) == pytest.approx(
        direction * 64 / 12
    )
    assert actuator_actions.position_to_motor_turns(actuator, -15) == pytest.approx(
        -direction * 64 / 24
    )
    assert actuator_actions.motor_turns_to_position(
        actuator, direction * 64 / 12
    ) == pytest.approx(30)
    assert actuator_actions.velocity_to_motor_turns(actuator, 15) == pytest.approx(
        direction * 64 / 24
    )
    assert actuator_actions.motor_turns_to_velocity(
        actuator, direction * 64 / 24
    ) == pytest.approx(15)


def test_inverted_asymmetric_bounds_are_sorted_on_raw_motor():
    _, motor = make_actuator("joint", inverted=True, minimum=-10, maximum=30)
    assert motor.position_min == pytest.approx(-64 / 12)
    assert motor.position_max == pytest.approx(64 / 36)


def test_knee_ballscrew_profile_maps_angles_and_caps_at_55_degrees():
    actuator, motor = make_knee_actuator()

    expected_turns = {
        -55: 12.3113908569,
        0: 6.7624856638,
        55: 0.4582607761,
    }
    for angle, turns in expected_turns.items():
        assert actuator_actions.position_to_motor_turns(
            actuator, angle
        ) == pytest.approx(turns)
        assert actuator_actions.motor_turns_to_position(
            actuator, turns
        ) == pytest.approx(angle, abs=1e-8)

    assert motor.position_min == pytest.approx(expected_turns[55])
    assert motor.position_max == pytest.approx(expected_turns[-55])
    with pytest.raises(ValueError):
        actuator_actions.validate_target_position(actuator, -55.001)
    with pytest.raises(ValueError):
        actuator_actions.validate_target_position(actuator, 55.001)


def test_knee_velocity_round_trip_uses_local_linkage_slope():
    actuator, _ = make_knee_actuator()
    position = actuator_actions.position_to_motor_turns(actuator, 20)
    raw_velocity = actuator_actions.velocity_to_motor_turns(
        actuator, 12.5, position_motor_turns=position
    )
    assert raw_velocity < 0
    assert actuator_actions.motor_turns_to_velocity(
        actuator, raw_velocity, position_motor_turns=position
    ) == pytest.approx(12.5)


def test_knee_x_offset_redefines_the_motor_zero_location():
    baseline, _ = make_knee_actuator("baseline", x_offset=0)
    baseline_turns = actuator_actions.position_to_motor_turns(baseline, 0)

    actuator_actions.ctx.store.clear()
    actuator_actions.ctx.stored_keys.clear()
    motion_profile_actions.ctx.store.clear()
    motion_profile_actions.ctx.stored_keys.clear()
    motor_actions.ctx.store.clear()
    motor_actions.ctx.stored_keys.clear()

    offset_actuator, offset_motor = make_knee_actuator("offset", x_offset=2.5)
    offset_turns = actuator_actions.position_to_motor_turns(offset_actuator, 0)

    assert offset_turns == pytest.approx(baseline_turns - 2.5)
    assert actuator_actions.motor_turns_to_position(
        offset_actuator, offset_turns
    ) == pytest.approx(0)
    assert offset_motor.position_min == pytest.approx(0.4582607761 - 2.5)
    assert offset_motor.position_max == pytest.approx(12.3113908569 - 2.5)


def test_boundaries_are_accepted_and_outside_targets_rejected():
    actuator, _ = make_actuator("joint")
    assert actuator_actions.validate_target_position(actuator, -40) == pytest.approx(
        -64 / 9
    )
    assert actuator_actions.validate_target_position(actuator, 40) == pytest.approx(
        64 / 9
    )
    with pytest.raises(ValueError):
        actuator_actions.validate_target_position(actuator, -40.001)
    with pytest.raises(ValueError):
        actuator_actions.validate_target_position(actuator, 40.001)


def test_trajectory_magnitudes_stay_positive_and_runtime_speeds_are_isolated():
    first, _ = make_actuator("first", inverted=True)
    second, _ = make_actuator("second", inverted=True)
    with patch.object(
        motor_actions, "set_trajectory_velocity", return_value=True
    ) as send:
        assert actuator_actions.set_trajectory_speed(first, 11.25) is True
    assert actuator_actions.get_trajectory_velocity_motor_turns(first) == pytest.approx(
        2
    )
    assert first.trajectory_velocity_motor_turns == pytest.approx(2)
    assert second.trajectory_velocity_motor_turns == 1
    assert send.call_args.args[1] == pytest.approx(2)

    with (
        patch.object(motor_actions, "set_controller_mode", return_value=True),
        patch.object(
            motor_actions, "set_trajectory_velocity", return_value=True
        ) as velocity,
        patch.object(motor_actions, "set_trajectory_accel", return_value=True) as accel,
    ):
        assert actuator_actions.configure_trajectory(second) is True
    assert velocity.call_args.args[1] == 1
    assert accel.call_args.args[1] == 1


def test_profile_and_competing_raw_bounds_are_rejected():
    with pytest.raises(ValueError):
        ActuatorMotionProfile(
            motor_turns_per_actuator_turn=0,
            position_min=quantity(-1, "degrees"),
            position_max=quantity(1, "degrees"),
            trajectory_velocity=quantity(1, "motor_turns_per_second"),
            trajectory_acceleration=quantity(1, "motor_turns_per_second_squared"),
        )
    _, motor = make_actuator("valid")
    motor.position_min = -1
    motor.position_max = 1
    with pytest.raises(ValueError, match="raw position bounds"):
        Actuator(motor="valid", profile="valid_profile")


def test_configuration_parser_accepts_explicit_quantities():
    parsed = motion_profile_actions.parse_motion_profile(
        {
            "motor_turns_per_actuator_turn": 64,
            "position_min": {"value": -40, "unit": "degrees"},
            "position_max": {"value": 40, "unit": "degrees"},
            "trajectory_velocity": {
                "value": 1,
                "unit": "motor_turns_per_second",
            },
            "trajectory_acceleration": {
                "value": 1,
                "unit": "motor_turns_per_second_squared",
            },
        },
        _identifier="profile",
    )
    assert parsed.motor_turns_per_actuator_turn == 64


def test_configuration_parser_accepts_knee_ballscrew_profile():
    parsed = motion_profile_actions.parse_motion_profile(
        {
            "position_min": {"value": -55, "unit": "degrees"},
            "position_max": {"value": 55, "unit": "degrees"},
            "trajectory_velocity": {
                "value": 1,
                "unit": "motor_turns_per_second",
            },
            "trajectory_acceleration": {
                "value": 1,
                "unit": "motor_turns_per_second_squared",
            },
            "ballscrew_linkage": {
                "L1": 7.235,
                "L2": 18.6452,
                "A": 11.869,
                "B": 7.95,
                "ballscrew_travel_per_motor_turn": {
                    "value": 10,
                    "unit": "millimeters",
                },
                "x_offset": {"value": 2.5, "unit": "centimeters"},
            },
        },
        _identifier="knee",
    )
    assert parsed.motor_turns_per_actuator_turn is None
    assert parsed.ballscrew_linkage.L2 == 18.6452
    assert parsed.ballscrew_linkage.x_offset.value == 2.5


def test_robot_configuration_assigns_nonlinear_profile_only_to_k_joints():
    config_path = FOUNDATION_ROOT / "pinconfig.json"
    with config_path.open() as config_file:
        config = json.load(config_file)

    knee_names = {"brk", "blk", "frk", "flk"}
    assigned = {
        name
        for name, actuator in config["actuator"].items()
        if actuator["profile"] == "knee_ballscrew"
    }
    assert assigned == knee_names
    profile = config["actuator_motion_profile"]["knee_ballscrew"]
    assert profile["position_min"] == {"value": -55, "unit": "degrees"}
    assert profile["position_max"] == {"value": 55, "unit": "degrees"}
    assert profile["ballscrew_linkage"]["x_offset"] == {
        "value": 6.7624856638,
        "unit": "centimeters",
    }
