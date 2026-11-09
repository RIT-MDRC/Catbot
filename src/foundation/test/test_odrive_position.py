"""Hardware-free tests for the ODrive position sample and controller helpers."""

import asyncio
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from textual.widgets import RichLog, Static

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
SAMPLES_ROOT = FOUNDATION_ROOT / "samples"
sys.path.insert(0, str(FOUNDATION_ROOT))
sys.path.insert(0, str(SAMPLES_ROOT))

import odrive_position_test as motor_test_sample
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
    CommandInput,
    MotorTestApp,
    describe_axis_error,
    describe_motors,
    find_motors,
    parse_angle_degrees,
    parse_speed_degrees_per_second,
    position_target_degrees,
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


def test_parse_speed_degrees_per_second() -> None:
    assert parse_speed_degrees_per_second("5.625") == 5.625
    for invalid_value in ("", "not-a-speed", "0", "-1", "nan", "inf", "-inf"):
        with pytest.raises(ValueError):
            parse_speed_degrees_per_second(invalid_value)


def test_parse_angle_degrees_rejects_empty_invalid_and_non_finite_values() -> None:
    assert parse_angle_degrees("30") == 30.0
    assert parse_angle_degrees("-15.5") == -15.5
    assert parse_angle_degrees("-41") == -41.0
    assert parse_angle_degrees("41") == 41.0

    for invalid_value in (
        "",
        "not-an-angle",
        "nan",
        "inf",
        "-inf",
    ):
        try:
            parse_angle_degrees(invalid_value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid angle was accepted: {invalid_value}")


def test_position_target_degrees_supports_absolute_and_relative_commands() -> None:
    assert position_target_degrees("mp", 15, -20) == 15
    assert position_target_degrees("mr", 15, -20) == -5
    assert position_target_degrees("mr", -5, 15) == 10

    with pytest.raises(ValueError, match="current position"):
        position_target_degrees("mr", 5)
    with pytest.raises(ValueError, match="unknown position command"):
        position_target_degrees("move", 5, 0)


def test_motor_test_tui_submits_commands_and_retains_history() -> None:
    commands = []

    def fake_run_motor_test(
        _args,
        read_command,
        emit,
        on_motors_configured,
        on_ready,
        should_stop,
    ) -> int:
        on_motors_configured({})
        on_ready()
        try:
            while not should_stop():
                command = read_command("angle> ")
                commands.append(command)
                emit(f"received {command}")
                if command == "q":
                    return 0
        except EOFError:
            return 0
        return 0

    async def exercise() -> None:
        app = MotorTestApp(Namespace(motor=None, config=Path("unused.json")))
        with patch.object(
            motor_test_sample, "run_motor_test", side_effect=fake_run_motor_test
        ):
            async with app.run_test() as pilot:
                await pilot.pause(0.1)
                command_input = app.query_one("#command", CommandInput)
                assert command_input.has_focus
                assert command_input.disabled is False

                await pilot.press("m", "p", "space", "1", "5", "space", "0", "enter")
                await pilot.pause(0.1)
                assert commands == ["mp 15 0"]

                command_input.value = ""
                await pilot.press("up")
                assert command_input.value == "mp 15 0"

                command_input.value = "q"
                await pilot.press("enter")
                await pilot.pause(0.1)

    asyncio.run(exercise())


def test_motor_test_tui_reports_can_error_changes() -> None:
    motor = SimpleNamespace(axisID=3, axis_error=0)

    def fake_run_motor_test(
        _args,
        read_command,
        emit,
        on_motors_configured,
        on_ready,
        should_stop,
    ) -> int:
        del emit, should_stop
        on_motors_configured({"front": motor})
        on_ready()
        try:
            read_command("angle> ")
        except EOFError:
            pass
        return 0

    async def exercise() -> None:
        app = MotorTestApp(Namespace(motor=None, config=Path("unused.json")))
        with patch.object(
            motor_test_sample, "run_motor_test", side_effect=fake_run_motor_test
        ):
            async with app.run_test() as pilot:
                await pilot.pause(0.1)
                status = app.query_one("#can-status", Static)
                assert "CAN OK" in str(status.render())

                motor.axis_error = 0x300
                app.refresh_can_status()
                assert "CAN ERRORS (1)" in str(status.render())
                log = app.query_one("#log", RichLog)
                rendered_log = "\n".join(line.text for line in log.lines)
                assert "front (axis 3): 0x300" in rendered_log
                assert "ENCODER_FAILED" in rendered_log
                assert "CONTROLLER_FAILED" in rendered_log

                motor.axis_error = 0
                app.refresh_can_status()
                rendered_log = "\n".join(line.text for line in log.lines)
                assert "CAN errors cleared" in rendered_log
                app.action_request_quit()
                await pilot.pause(0.1)

    asyncio.run(exercise())


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


def test_find_motors_accepts_comma_separated_names_and_axis_ids() -> None:
    first = make_motor()
    second = make_motor()
    second.axisID = 2
    third = make_motor()
    third.axisID = 3
    motors = {"front": first, "middle": second, "rear": third}

    assert find_motors(motors, "front, 2,rear") == [
        ("front", first),
        ("middle", second),
        ("rear", third),
    ]


def test_find_motors_comma_selection_is_atomic_and_deduplicated() -> None:
    first = make_motor()
    second = make_motor()
    second.axisID = 2
    motors = {"front": first, "rear": second}

    assert find_motors(motors, "front,front,2") == [
        ("front", first),
        ("rear", second),
    ]
    assert find_motors(motors, "front,missing") == []
    assert find_motors(motors, "front,,rear") == []


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
    faulted.axis_error = 0x300

    assert report_bus_errors({"healthy": healthy, "faulted": faulted}) is True
    output = capsys.readouterr().out
    assert "faulted (axis 4): 0x300 ([ENCODER_FAILED, CONTROLLER_FAILED])" in output


def test_describe_axis_error_preserves_unknown_bits() -> None:
    assert describe_axis_error(0x1000000) == "[UNKNOWN_BITS_0x1000000]"


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
