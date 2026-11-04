"""Hardware-free tests for the ODrive position sample and controller helpers."""

from pathlib import Path
import sys
from unittest.mock import Mock, patch

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
SAMPLES_ROOT = FOUNDATION_ROOT / "samples"
sys.path.insert(0, str(FOUNDATION_ROOT))
sys.path.insert(0, str(SAMPLES_ROOT))

from component.motor import motor_actions
from component.motor.odrive_enums import ControlMode, InputMode, MotorState
from component.motor.odrive_motor import (
    ODriveMotor,
    read_heartbeat,
    report_controller_error,
    report_encoder_error,
    report_motor_error,
    report_sensorless_error,
    update_estimates,
)
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
    motor.strict_bounds = False
    motor.axis_error = 0
    motor.current_state = MotorState.UNDEFINED
    motor.current_position = None
    motor.current_velocity = None
    motor.last_heartbeat_time = None
    motor.last_encoder_estimate_time = None
    motor.motor_error = 0
    motor.encoder_error = 0
    motor.sensorless_error = 0
    motor.controller_error = 0
    motor.motor_error_flag = False
    motor.encoder_error_flag = False
    motor.sensorless_error_flag = False
    motor.controller_error_flag = False
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


def test_find_motors_wildcard_returns_every_motor_by_axis_id() -> None:
    first = make_motor()
    first.axisID = 7
    second = make_motor()
    second.axisID = 2

    assert find_motors({"later": first, "earlier": second}, "*") == [
        ("earlier", second),
        ("later", first),
    ]


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


def test_feedback_handlers_retain_timestamps_and_detailed_errors() -> None:
    motor = make_motor()
    heartbeat = {
        "Axis_State": Mock(value=MotorState.IDLE),
        "Axis_Error": 0x1C0,
        "Motor_Error_Flag": 1,
        "Encoder_Error_Flag": 1,
        "Controller_Error_Flag": 1,
    }
    with patch("component.motor.odrive_motor.time.monotonic", return_value=12.5):
        read_heartbeat(motor, heartbeat)
        update_estimates(motor, {"Pos_Estimate": 1.5, "Vel_Estimate": -0.25})

    report_motor_error(motor, {"Motor_Error": 8})
    report_encoder_error(motor, {"Encoder_Error": 4})
    report_sensorless_error(motor, {"Sensorless_Error": 2})
    report_controller_error(motor, {"Controller_Error": 1})

    assert motor.last_heartbeat_time == 12.5
    assert motor.last_encoder_estimate_time == 12.5
    assert motor.current_position == 1.5
    assert motor.current_velocity == -0.25
    assert motor.motor_error == 8
    assert motor.encoder_error == 4
    assert motor.sensorless_error == 2
    assert motor.controller_error == 1
    assert motor.motor_error_flag is True
    assert motor.encoder_error_flag is True
    assert motor.sensorless_error_flag is True
    assert motor.controller_error_flag is True


def test_request_error_details_requests_every_flagged_message() -> None:
    motor = make_motor()
    motor.motor_error_flag = True
    motor.encoder_error_flag = True
    motor.controller_error_flag = True
    with patch.object(motor_actions, "request_message", return_value=True) as request:
        assert motor_actions.request_error_details(motor) is True

    assert [call.args[1] for call in request.call_args_list] == [
        "Get_Motor_Error",
        "Get_Encoder_Error",
        "Get_Controller_Error",
    ]


def test_clear_errors_resets_cached_detailed_errors_after_success() -> None:
    motor = make_motor()
    motor.motor_error = 8
    motor.encoder_error = 4
    motor.sensorless_error = 2
    motor.controller_error = 1
    with patch.object(motor_actions, "send_message", return_value=True):
        assert motor_actions.clear_error_message(motor) is True

    assert (
        motor.motor_error,
        motor.encoder_error,
        motor.sensorless_error,
        motor.controller_error,
    ) == (0, 0, 0, 0)
