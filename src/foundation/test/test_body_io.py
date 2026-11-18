"""Foundation service validation and immediate I/O, without ROS or CAN hardware."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest


@pytest.fixture
def body_io(monkeypatch):
    root = Path(__file__).parents[1] / "foundation"
    monkeypatch.syspath_prepend(str(root))
    modules = {
        "rclpy": {},
        "rclpy.node": {"Node": object},
        "rclpy.qos": dict.fromkeys(
            ("DurabilityPolicy", "HistoryPolicy", "QoSProfile", "ReliabilityPolicy"),
            object,
        ),
        "catbot_interfaces.msg": dict.fromkeys(
            (
                "ActuatorErrorState",
                "ActuatorKinematicState",
                "ActuatorPositionCommand",
                "BodyErrorState",
                "BodyKinematicState",
            ),
            object,
        ),
        "catbot_interfaces.srv": {"MotorCommand": object},
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location(
        "body_io_under_test", root / "main.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    snapshots = {
        name: SimpleNamespace(
            current_state=module.MotorState.IDLE,
            axis_error=0,
            last_heartbeat_time=10.0,
            current_position=0.0,
            current_velocity=0.0,
            last_encoder_estimate_time=10.0,
        )
        for name in ("a", "b")
    }
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.1)
    monkeypatch.setattr(module, "HEARTBEAT_STALE_SECONDS", 0.4)
    monkeypatch.setattr(module, "ENCODER_STALE_SECONDS", 0.2)
    monkeypatch.setattr(
        module.motor_actions, "get_state_snapshot", snapshots.__getitem__
    )
    for owner, name in (
        (module.motor_actions, "set_axis_state"),
        (module.motor_actions, "clear_error_message"),
        (module.motor_actions, "hold_current_position"),
        (module.actuator_actions, "configure_trajectory"),
    ):
        monkeypatch.setattr(owner, name, Mock(return_value=True))
    node = SimpleNamespace(actuator_names=("a", "b"), ordered_motor_names=["a", "b"])
    return module, node, snapshots


def command(body_io, operation, names=(), state=0):
    module, node, _ = body_io
    return module.BodyControlNode._motor_command(
        node,
        SimpleNamespace(operation=operation, actuator_names=names, state=state),
        SimpleNamespace(),
    )


@pytest.mark.parametrize(
    "fault",
    ["unknown", "duplicate", "operation", "state", "heartbeat", "axis", "encoder"],
)
def test_invalid_batch_sends_no_motor_commands(body_io, fault):
    module, _, snapshots = body_io
    operation, names, state = "state", ["a", "b"], 8
    if fault == "unknown":
        names[1] = "missing"
    elif fault == "duplicate":
        names[1] = "a"
    elif fault == "operation":
        operation = "startup"
    elif fault == "state":
        state = 2
    elif fault == "heartbeat":
        snapshots["b"].last_heartbeat_time = 0
    elif fault == "axis":
        snapshots["b"].axis_error = 1
    else:
        snapshots["b"].last_encoder_estimate_time = 0.0
    response = command(body_io, operation, names, state)
    assert not response.success
    module.motor_actions.set_axis_state.assert_not_called()
    module.motor_actions.hold_current_position.assert_not_called()
    module.motor_actions.clear_error_message.assert_not_called()
    module.actuator_actions.configure_trajectory.assert_not_called()


@pytest.mark.parametrize(
    "operation,state,action",
    [
        ("state", 4, "set_axis_state"),
        ("hold", 0, "hold_current_position"),
        ("trajectory", 0, "configure_trajectory"),
        ("clear_errors", 0, "clear_error_message"),
    ],
)
def test_valid_sparse_command_routes_only_to_requested_actuator(
    body_io, operation, state, action
):
    module, _, _ = body_io
    response = command(body_io, operation, ["b"], state)
    assert response.success
    actions = {
        "set_axis_state": module.motor_actions.set_axis_state,
        "hold_current_position": module.motor_actions.hold_current_position,
        "configure_trajectory": module.actuator_actions.configure_trajectory,
        "clear_error_message": module.motor_actions.clear_error_message,
    }
    for name, send in actions.items():
        if name != action:
            send.assert_not_called()
        elif operation == "state":
            send.assert_called_once_with("b", module.MotorState.MOTOR_CALIBRATION)
        else:
            send.assert_called_once_with("b")


def test_idle_attempts_complete_roster_even_when_unresponsive_or_faulted(body_io):
    module, _, snapshots = body_io
    snapshots["a"].axis_error = 1
    snapshots["b"].last_heartbeat_time = None
    assert command(body_io, "idle").success
    assert module.motor_actions.set_axis_state.call_args_list == [
        call("a", module.MotorState.IDLE),
        call("b", module.MotorState.IDLE),
    ]
    module.motor_actions.clear_error_message.assert_not_called()


def test_send_failures_are_reported_without_any_followup_sequence(body_io):
    module, _, _ = body_io
    module.motor_actions.set_axis_state.side_effect = [True, False]
    response = command(body_io, "state", state=4)
    assert not response.success and "b" in response.message
    assert module.motor_actions.set_axis_state.call_count == 2
    module.motor_actions.hold_current_position.assert_not_called()
    module.actuator_actions.configure_trajectory.assert_not_called()
