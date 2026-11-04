"""Hardware-free tests for sparse body position command validation."""

from pathlib import Path
from types import SimpleNamespace
import math
import sys

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
sys.path.insert(0, str(FOUNDATION_ROOT))

from body_control import (
    degrees_to_motor_turns,
    motors_by_axis_id,
    prepare_position_targets,
)


def make_motor(
    axis_id: int,
    *,
    axis_error: int = 0,
    position_min: float = -41.0,
    position_max: float = 41.0,
):
    """Create the subset of motor state used by command validation."""
    return SimpleNamespace(
        axisID=axis_id,
        axis_error=axis_error,
        position_min=position_min,
        position_max=position_max,
    )


def test_degrees_to_motor_turns_uses_current_scale() -> None:
    assert degrees_to_motor_turns(30.0) == 5.33
    assert degrees_to_motor_turns(-15.0) == -2.665


def test_motors_are_ordered_by_unique_axis_id() -> None:
    motors = {"rear": make_motor(4), "front": make_motor(1)}
    assert [name for name, _ in motors_by_axis_id(motors)] == ["front", "rear"]


def test_duplicate_axis_ids_are_rejected() -> None:
    motors = {"left": make_motor(1), "right": make_motor(1)}
    try:
        motors_by_axis_id(motors)
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate CAN axis IDs were accepted")


def test_sparse_command_only_returns_named_actuators() -> None:
    motors = {"bra": make_motor(0), "bla": make_motor(1)}
    targets = prepare_position_targets(["bla"], [30.0], motors, {"bra", "bla"})
    assert targets == [("bla", 5.33)]


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
        (["bra"], [300.0]),
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
