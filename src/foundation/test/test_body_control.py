"""Hardware-free tests for sparse body position command validation."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
sys.path.insert(0, str(FOUNDATION_ROOT))

from body_control import (
    actuators_by_axis_id,
    prepare_position_targets,
)
from component.actuator import actuator_actions, motion_profile_actions
from component.actuator.actuator import Actuator
from component.actuator.motion_profile import ActuatorMotionProfile, MotionQuantity
from component.motor import motor_actions


def make_motor(
    axis_id: int,
    *,
    axis_error: int = 0,
    position_min: float = -(64 * 40 / 360),
    position_max: float = 64 * 40 / 360,
    inverted: bool = False,
):
    """Create the subset of motor state used by command validation."""
    motor = SimpleNamespace(
        axisID=axis_id,
        axis_error=axis_error,
        position_min=position_min,
        position_max=position_max,
    )
    name = f"motor_{len(motor_actions.ctx.store)}"
    profile_name = f"profile_{len(motion_profile_actions.ctx.store)}"
    motor_actions.ctx.store[name] = motor
    motor_actions.ctx.stored_keys.add(name)
    motion_profile_actions.ctx.store[profile_name] = ActuatorMotionProfile(
        motor_turns_per_actuator_turn=64,
        position_min=MotionQuantity(position_min * 360 / 64, "degrees"),
        position_max=MotionQuantity(position_max * 360 / 64, "degrees"),
        trajectory_velocity=MotionQuantity(1, "motor_turns_per_second"),
        trajectory_acceleration=MotionQuantity(1, "motor_turns_per_second_squared"),
        inverted=inverted,
    )
    motion_profile_actions.ctx.stored_keys.add(profile_name)
    motor.position_min = None
    motor.position_max = None
    actuator = Actuator(motor=name, profile=profile_name)
    motor.axis_error = axis_error
    return actuator


@pytest.fixture(autouse=True)
def clear_component_stores():
    contexts = (actuator_actions.ctx, motion_profile_actions.ctx, motor_actions.ctx)
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


def test_motors_are_ordered_by_unique_axis_id() -> None:
    motors = {"rear": make_motor(4), "front": make_motor(1)}
    assert [name for name, _ in actuators_by_axis_id(motors)] == ["front", "rear"]


def test_duplicate_axis_ids_are_rejected() -> None:
    motors = {"left": make_motor(1), "right": make_motor(1)}
    try:
        actuators_by_axis_id(motors)
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate CAN axis IDs were accepted")


def test_sparse_command_only_returns_named_actuators() -> None:
    motors = {"bra": make_motor(0), "bla": make_motor(1)}
    targets = prepare_position_targets(["bla"], [30.0], motors, {"bra", "bla"})
    assert targets == [("bla", 30.0)]


def test_sparse_target_uses_selected_inverted_profile_direction() -> None:
    actuator = make_motor(0, inverted=True)
    targets = prepare_position_targets(
        ["joint"], [30.0], {"joint": actuator}, {"joint"}
    )
    with patch.object(motor_actions, "set_target_position", return_value=True) as send:
        assert actuator_actions.set_target_position(actuator, targets[0][1]) is True
    assert send.call_args.args[1] == pytest.approx(-64 / 12)


def test_faulted_omitted_actuator_does_not_block_command() -> None:
    motors = {"healthy": make_motor(0), "faulted": make_motor(1, axis_error=0x100)}
    assert prepare_position_targets(["healthy"], [0.0], motors, {"healthy"}) == [
        ("healthy", 0.0)
    ]


def test_invalid_sparse_commands_are_rejected_before_targets_are_returned() -> None:
    motors = {"bra": make_motor(0)}
    invalid_commands = [
        ([], []),
        (["bra"], []),
        (["bra", "bra"], [0.0, 1.0]),
        (["missing"], [0.0]),
        (["bra"], [math.nan]),
        (["bra"], [-40.0001]),
        (["bra"], [40.0001]),
    ]
    for names, positions in invalid_commands:
        try:
            prepare_position_targets(names, positions, motors, {"bra"})
        except ValueError:
            continue
        raise AssertionError(f"invalid command was accepted: {names}, {positions}")


def test_unready_or_faulted_requested_actuator_is_rejected() -> None:
    healthy = {"bra": make_motor(0)}
    faulted = {"bra": make_motor(0, axis_error=1)}
    for motors, ready in ((healthy, set()), (faulted, {"bra"})):
        try:
            prepare_position_targets(["bra"], [0.0], motors, ready)
        except ValueError:
            continue
        raise AssertionError("unready or faulted actuator was accepted")
