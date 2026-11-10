"""Hardware-free tests for the ODrive position sample and controller helpers."""

import asyncio
import json
import subprocess
import sys
import textwrap
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from textual.widgets import Static, TextArea
from textual.widgets.text_area import Selection

FOUNDATION_ROOT = Path(__file__).resolve().parents[1] / "foundation"
SAMPLES_ROOT = FOUNDATION_ROOT / "samples"
sys.path.insert(0, str(FOUNDATION_ROOT))
sys.path.insert(0, str(SAMPLES_ROOT))

import odrive_position_test as motor_test_sample
from component.actuator import actuator_actions, motion_profile_actions
from component.actuator.actuator import Actuator
from component.can import can_actions
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
    motor_fault_values,
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


def test_sample_import_registers_parsers_without_opening_can(tmp_path) -> None:
    """Check registration in a fresh process, before configuration or commands."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import sys
                from unittest.mock import patch

                sys.path.insert(0, sys.argv[1])
                with patch("can.Bus", side_effect=AssertionError("CAN opened during import")):
                    import odrive_position_test

                from state_management import get_context

                for name in ("can_bus", "odrive_motor", "actuator_motion_profile", "actuator"):
                    context = get_context(name)
                    assert context is not None, name
                    assert context.parse_device is not None, name
                    assert not context.store, name
                """),
            str(SAMPLES_ROOT),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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
    motors = {
        "front": motor,
        "flf": SimpleNamespace(axisID=8, axis_error=0),
        "frf": SimpleNamespace(axisID=9, axis_error=0),
    }

    def fake_run_motor_test(
        _args,
        read_command,
        emit,
        on_motors_configured,
        on_ready,
        should_stop,
    ) -> int:
        del emit, should_stop
        on_motors_configured(
            {name: SimpleNamespace(**vars(state)) for name, state in motors.items()}
        )
        on_ready()
        try:
            read_command("angle> ")
        except EOFError:
            pass
        return 0

    async def exercise() -> None:
        app = MotorTestApp(Namespace(motor=None, config=Path("unused.json")))
        with (
            patch.object(
                motor_test_sample, "run_motor_test", side_effect=fake_run_motor_test
            ),
            patch.object(
                motor_actions,
                "get_state_snapshot",
                side_effect=lambda name: SimpleNamespace(**vars(motors[name])),
            ),
            patch.object(
                motor_actions, "request_error_details", return_value=True
            ) as request_details,
        ):
            async with app.run_test() as pilot:
                await pilot.pause(0.1)
                status = app.query_one("#can-status", Static)
                assert "CAN OK" in str(status.render())

                motor.axis_error = 0x300
                app.refresh_can_status()
                assert "CAN ERRORS (1)" in str(status.render())
                log = app.query_one("#log", TextArea)
                rendered_log = log.text
                assert "front (axis 3): axis=0x300" in rendered_log
                assert "ENCODER_FAILED" in rendered_log
                assert "CONTROLLER_FAILED" in rendered_log

                motor.axis_error = 0
                motor.motor_error_flag = True
                app.refresh_can_status()
                assert "CAN ERRORS (1)" in str(status.render())
                assert "motor=flagged" in log.text
                request_details.assert_called_once_with("front")
                app.refresh_can_status()
                request_details.assert_called_once_with("front")

                motor.motor_error = 8
                app.refresh_can_status()
                assert "motor=0x8" in log.text

                motor.motor_error_flag = False
                motor.motor_error = 0
                app.refresh_can_status()
                rendered_log = log.text
                assert "CAN errors cleared" in rendered_log

                motors["flf"].axis_error = 0x1000
                motors["frf"].axis_error = 0x2000
                app.refresh_can_status()
                assert "CAN ERRORS (2)" in str(status.render())
                assert "flf (axis 8): axis=0x1000 [MIN_ENDSTOP_PRESSED]" in log.text
                assert "frf (axis 9): axis=0x2000 [MAX_ENDSTOP_PRESSED]" in log.text

                motors["flf"].axis_error = 0
                app.refresh_can_status()
                assert "CAN ERRORS (1)" in str(status.render())
                motors["frf"].axis_error = 0
                app.refresh_can_status()
                assert "CAN OK" in str(status.render())

                log.focus()
                log.selection = Selection((0, 0), (0, 5))
                await pilot.press("ctrl+c")
                assert app.clipboard == log.text[:5]
                assert app.stop_event.is_set() is False
                app.action_request_quit()
                await pilot.pause(0.1)

    asyncio.run(exercise())


def test_motor_fault_values_include_detail_errors_and_heartbeat_flags() -> None:
    motor = make_motor()
    motor.controller_error = 0x20
    motor.encoder_error_flag = True

    values = motor_fault_values(motor)

    assert values[4] == 0x20
    assert values[6] == 1


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


def test_hold_current_position_uses_feedback_without_logical_bounds() -> None:
    motor = make_motor()
    motor.current_position = 123.0
    motor.position_min = -1.0
    motor.position_max = 1.0
    with patch.object(motor_actions, "send_message", return_value=True) as send:
        assert motor_actions.hold_current_position(motor) is True

    send.assert_called_once_with(
        motor,
        "Set_Input_Pos",
        {"Input_Pos": 123.0, "Vel_FF": 0.0, "Torque_FF": 0.0},
    )


def test_hold_current_position_requires_encoder_feedback() -> None:
    motor = make_motor()
    motor.current_position = None
    with patch.object(motor_actions, "send_message") as send:
        assert motor_actions.hold_current_position(motor) is False

    send.assert_not_called()


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


@pytest.fixture
def command_runtime(monkeypatch):
    """Exercise real command dispatch with simulated CAN and actuator actions."""
    front = make_motor()
    rear = make_motor()
    rear.axisID = 1
    for motor in (front, rear):
        motor.current_state = MotorState.IDLE
        motor.current_position = 0.0
        motor.current_velocity = 0.5
    motors = {"front": front, "rear": rear}
    output = []

    def set_state(name, state):
        motors[name].current_state = state
        return True

    actions = SimpleNamespace(
        configure=Mock(return_value=True),
        hold=Mock(return_value=True),
        set_state=Mock(side_effect=set_state),
        clear=Mock(return_value=True),
        set_speed=Mock(return_value=True),
        position=Mock(return_value=10.0),
        velocity=Mock(return_value=5.0),
        validate=Mock(side_effect=lambda _name, degrees: degrees * 64 / 360),
        target=Mock(return_value=True),
        close=Mock(),
    )
    monkeypatch.setattr(motor_test_sample, "configure_device", Mock())
    monkeypatch.setattr(can_actions, "get_names", lambda: ["can0"])
    monkeypatch.setattr(can_actions, "close", actions.close)
    monkeypatch.setattr(motor_actions, "get_names", lambda: list(motors))
    monkeypatch.setattr(motor_actions, "get_state_snapshot", motors.__getitem__)
    monkeypatch.setattr(motor_actions, "hold_current_position", actions.hold)
    monkeypatch.setattr(motor_actions, "set_axis_state", actions.set_state)
    monkeypatch.setattr(motor_actions, "clear_error_message", actions.clear)
    monkeypatch.setattr(actuator_actions, "configure_trajectory", actions.configure)
    monkeypatch.setattr(actuator_actions, "set_trajectory_speed", actions.set_speed)
    monkeypatch.setattr(actuator_actions, "get_current_position", actions.position)
    monkeypatch.setattr(actuator_actions, "get_current_velocity", actions.velocity)
    monkeypatch.setattr(actuator_actions, "validate_target_position", actions.validate)
    monkeypatch.setattr(actuator_actions, "set_target_position", actions.target)
    monkeypatch.setattr(
        actuator_actions, "get_trajectory_velocity_motor_turns", lambda _name: 2.0
    )
    monkeypatch.setattr(
        motor_test_sample,
        "wait_for",
        lambda name, predicate, _timeout, _stop: predicate(motors[name]),
    )
    # Patch only this sample's clock so UI timing in other tests stays intact.
    monkeypatch.setattr(
        motor_test_sample, "time", SimpleNamespace(sleep=lambda _: None)
    )

    def run(commands, selector="*"):
        commands = iter(commands)

        def read_command(_prompt):
            command = next(commands, EOFError())
            if isinstance(command, BaseException):
                raise command
            return command

        return motor_test_sample.run_motor_test(
            Namespace(motor=selector, config=Path("unused.json")),
            read_command=read_command,
            emit=output.append,
        )

    return SimpleNamespace(motors=motors, actions=actions, output=output, run=run)


def test_command_session_dispatches_aliases_and_position_commands(command_runtime):
    runtime = command_runtime

    assert (
        runtime.run(
            ["R 0", "rs rear", "speed 12 0,1", "a", "mp 15 front", "mr -5 1", "d", "q"]
        )
        == 0
    )

    runtime.actions.position.assert_any_call("front")
    runtime.actions.velocity.assert_called_once_with("rear")
    assert runtime.actions.set_speed.call_args_list == [
        (("front", 12.0),),
        (("rear", 12.0),),
    ]
    assert runtime.actions.target.call_args_list == [
        (("front", 15.0),),
        (("rear", 5.0),),
    ]
    assert all(m.current_state == MotorState.IDLE for m in runtime.motors.values())
    runtime.actions.close.assert_called_once_with("can0")


@pytest.mark.parametrize("command", ["r", "read", "rs", "read-speed"])
@pytest.mark.parametrize("motor_turns", [100.0, -16.189464569091797])
def test_read_keeps_session_open_when_knee_feedback_cannot_convert(
    command_runtime, command, motor_turns
):
    runtime = command_runtime
    config = json.loads(motor_test_sample.DEFAULT_CONFIG.read_text())
    actuator = object.__new__(Actuator)
    actuator.profile = motion_profile_actions.parse_motion_profile(
        config["actuator_motion_profile"]["knee_ballscrew"], "test_knee_profile"
    )
    runtime.motors["front"].current_position = motor_turns

    def position(name):
        if name == "front":
            return actuator_actions.motor_turns_to_position(actuator, motor_turns)
        return 10.0

    def velocity(name):
        if name == "front":
            return actuator_actions.motor_turns_to_velocity(
                actuator, 1.0, position_motor_turns=motor_turns
            )
        return 5.0

    runtime.actions.position.side_effect = position
    runtime.actions.velocity.side_effect = velocity

    assert runtime.run([f"{command} *", "read rear", "q"]) == 0

    assert any("unreachable linkage configuration" in line for line in runtime.output)
    assert any("rear: 10.00 degrees" in line for line in runtime.output)
    if command in ("rs", "read-speed"):
        assert any(
            "front: joint speed unavailable" in line and "motor turns/second" in line
            for line in runtime.output
        )
        assert any("rear: 5.00 degrees/second" in line for line in runtime.output)
    else:
        assert any(
            "front:" in line and f"{motor_turns:.4f} motor turns" in line
            for line in runtime.output
        )
        assert sum("rear: 10.00 degrees" in line for line in runtime.output) == 2
    runtime.actions.set_state.assert_not_called()
    runtime.actions.target.assert_not_called()


@pytest.mark.parametrize("command", ["read", "read-speed"])
def test_read_handles_unavailable_logical_feedback(command_runtime, command):
    runtime = command_runtime
    runtime.actions.position.side_effect = (
        [None, 10.0, 10.0] if command == "read" else [10.0]
    )
    runtime.actions.velocity.side_effect = [None, 5.0]

    assert runtime.run([f"{command} *", "read rear", "q"]) == 0

    assert any("No encoder" in line and "front" in line for line in runtime.output)
    assert any("rear: 10.00 degrees" in line for line in runtime.output)
    runtime.actions.set_state.assert_not_called()


def test_command_session_checks_each_selected_motor_before_motion(command_runtime):
    runtime = command_runtime
    runtime.motors["rear"].axis_error = 0x100

    assert runtime.run(["mp 5", "arm", "mp 5", "q"]) == 0

    runtime.actions.hold.assert_called_once_with("front")
    runtime.actions.target.assert_called_once_with("front", 5.0)
    assert "rear" not in [
        call.args[0] for call in runtime.actions.set_state.call_args_list
    ]
    assert "front is disarmed; run 'arm front'." in runtime.output
    assert runtime.motors["front"].current_state == MotorState.IDLE


def test_command_session_rejects_invalid_values_and_atomic_selections(command_runtime):
    runtime = command_runtime

    assert (
        runtime.run(
            [
                "",
                "15",
                "speed nan",
                "mp inf",
                "mr",
                "arm front,missing",
                "speed 5 7",
                "q",
            ],
            selector=None,
        )
        == 0
    )

    runtime.actions.set_state.assert_not_called()
    runtime.actions.target.assert_not_called()
    runtime.actions.set_speed.assert_not_called()
    assert any("Configured motors:" in line for line in runtime.output)


def test_command_session_rejects_relative_motion_without_feedback(command_runtime):
    runtime = command_runtime
    runtime.actions.position.return_value = None

    assert runtime.run(["arm front", "mr 5 front", "q"]) == 0

    runtime.actions.target.assert_not_called()
    assert any(
        "relative motion requires a current position" in line for line in runtime.output
    )


def test_command_session_rejects_out_of_bounds_targets(command_runtime):
    runtime = command_runtime
    runtime.actions.validate.side_effect = ValueError("outside configured bounds")

    assert runtime.run(["arm front", "mp 90 front", "q"]) == 0

    runtime.actions.target.assert_not_called()
    assert "Command rejected for front: outside configured bounds." in runtime.output


def test_command_session_returns_idle_after_unconfirmed_arm(
    command_runtime, monkeypatch
):
    runtime = command_runtime
    monkeypatch.setattr(
        motor_test_sample,
        "wait_for",
        lambda _name, _predicate, _timeout, _stop: False,
    )

    assert runtime.run(["arm front", "mp 5 front", "q"], selector=None) == 0

    runtime.actions.target.assert_not_called()
    assert runtime.motors["front"].current_state == MotorState.IDLE
    assert "front did not confirm that it is armed." in runtime.output


@pytest.mark.parametrize(
    "ending, expected_code",
    [("q", 0), (EOFError(), 0), (KeyboardInterrupt(), 0), (OSError("disconnected"), 7)],
)
def test_command_session_cleans_up_on_every_exit(
    command_runtime, ending, expected_code
):
    runtime = command_runtime

    assert runtime.run(["arm front", ending]) == expected_code

    assert runtime.actions.set_state.call_args_list[-1].args == (
        "front",
        MotorState.IDLE,
    )
    runtime.actions.close.assert_called_once_with("can0")


@pytest.mark.parametrize(
    "command, state",
    [
        ("c", MotorState.MOTOR_CALIBRATION),
        ("calibrate", MotorState.MOTOR_CALIBRATION),
        ("f", MotorState.FULL_CALIBRATION_SEQUENCE),
        ("full", MotorState.FULL_CALIBRATION_SEQUENCE),
        ("full-calibration", MotorState.FULL_CALIBRATION_SEQUENCE),
        ("h", MotorState.HOMING),
        ("home", MotorState.HOMING),
    ],
)
def test_command_session_dispatches_state_shortcuts(command_runtime, command, state):
    runtime = command_runtime

    assert runtime.run([f"{command} rear", "e rear", "q"]) == 0

    runtime.actions.set_state.assert_called_once_with("rear", state)
    runtime.actions.clear.assert_called_once_with("rear")
