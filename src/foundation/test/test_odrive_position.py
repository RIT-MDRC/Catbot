"""Hardware-free tests for the ODrive position sample and controller helpers."""

from pathlib import Path
import sys
from unittest.mock import patch

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
SAMPLES_ROOT = FOUNDATION_ROOT / "samples"
sys.path.insert(0, str(FOUNDATION_ROOT))
sys.path.insert(0, str(SAMPLES_ROOT))

from component.motor import motor_actions
from component.motor.odrive_enums import ControlMode, InputMode
from component.motor.odrive_motor import ODriveMotor
from odrive_position_test import (
    degrees_to_motor_turns,
    describe_motors,
    find_motors,
    report_bus_errors,
)


def make_motor() -> ODriveMotor:
    """Create an ODrive instance without opening a CAN interface."""
    motor = object.__new__(ODriveMotor)
    motor.axisID = 0
    motor.control_mode = ControlMode.VELOCITY_CONTROL
    motor.input_mode = InputMode.PASSTHROUGH
    motor.position_min = -35.0
    motor.position_max = 35.0
    return motor


def test_degrees_to_motor_turns() -> None:
    assert degrees_to_motor_turns(0) == 0
    assert degrees_to_motor_turns(30) == 5.33
    assert degrees_to_motor_turns(-15) == -2.665


def test_describe_motors_includes_names_and_axis_ids() -> None:
    first = make_motor()
    second = make_motor()
    second.axisID = 7

    assert describe_motors({"odrive_7": second, "odrive_1": first}) == (
        "odrive_1 (axis 0), odrive_7 (axis 7)"
    )


def test_find_motors_accepts_name_or_axis_id() -> None:
    first = make_motor()
    second = make_motor()
    second.axisID = 7
    motors = {"front": first, "rear": second}

    assert find_motors(motors, "front") == [("front", first)]
    assert find_motors(motors, "7") == [("rear", second)]
    assert find_motors(motors, "missing") == []


def test_find_motors_reports_duplicate_axis_ids() -> None:
    first = make_motor()
    second = make_motor()

    assert find_motors({"first": first, "second": second}, "0") == [
        ("first", first),
        ("second", second),
    ]


def test_report_bus_errors_lists_faulted_motors(capsys) -> None:
    healthy = make_motor()
    healthy.axis_error = 0
    faulted = make_motor()
    faulted.axisID = 4
    faulted.axis_error = 0x100

    assert report_bus_errors({"healthy": healthy, "faulted": faulted}) is True
    assert "faulted (axis 4): 0x100" in capsys.readouterr().out


def test_controller_mode_preserves_omitted_input_mode() -> None:
    motor = make_motor()
    with patch.object(motor_actions, "send_message", return_value=True) as send:
        result = motor_actions.set_controller_mode(motor, ControlMode.POSITION_CONTROL)

    assert result is True
    assert motor.control_mode == ControlMode.POSITION_CONTROL
    assert motor.input_mode == InputMode.PASSTHROUGH
    send.assert_called_once_with(
        motor,
        "Set_Controller_Mode",
        {
            "Control_Mode": ControlMode.POSITION_CONTROL,
            "Input_Mode": InputMode.PASSTHROUGH,
        },
    )


def test_controller_mode_does_not_update_after_failed_send() -> None:
    motor = make_motor()
    with patch.object(motor_actions, "send_message", return_value=False):
        result = motor_actions.set_controller_mode(
            motor,
            ControlMode.POSITION_CONTROL,
            InputMode.TRAP_TRAJ,
        )

    assert result is False
    assert motor.control_mode == ControlMode.VELOCITY_CONTROL
    assert motor.input_mode == InputMode.PASSTHROUGH
