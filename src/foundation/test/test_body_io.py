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
        "rclpy.executors": {
            "ExternalShutdownException": type(
                "ExternalShutdownException", (Exception,), {}
            )
        },
        "rclpy.signals": {"SignalHandlerOptions": SimpleNamespace(NO=0)},
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
            axis_id=axis_id,
            current_state=module.MotorState.IDLE,
            axis_error=0,
            last_heartbeat_time=10.0,
            current_position=0.0,
            current_velocity=0.0,
            last_encoder_estimate_time=10.0,
        )
        for axis_id, name in enumerate(("a", "b"))
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
        (module.motor_actions, "hold_after_fault"),
        (module.actuator_actions, "configure_trajectory"),
    ):
        monkeypatch.setattr(owner, name, Mock(return_value=True))
    node = SimpleNamespace(
        actuator_names=("a", "b"),
        ordered_motor_names=["a", "b"],
        motion_inhibited=False,
        emergency_disarm=False,
        invalid_kinematics=set(),
    )
    node._ready_motor_names = lambda **kwargs: (
        module.BodyControlNode._ready_motor_names(node, **kwargs)
    )
    logger = SimpleNamespace(error=Mock())
    node.get_logger = lambda: logger
    monkeypatch.setattr(module, "kinematic_values", Mock(return_value=(True, 0.0, 0.0)))
    monkeypatch.setattr(
        module.actuator_actions, "validate_target_position", Mock(return_value=0.0)
    )
    monkeypatch.setattr(
        module.actuator_actions, "set_target_position", Mock(return_value=True)
    )
    return module, node, snapshots


def test_unconvertible_feedback_blocks_position_control_without_motor_writes(body_io):
    module, node, snapshots = body_io
    for motor in snapshots.values():
        motor.current_state = module.MotorState.CLOSED_LOOP_CONTROL
    module.kinematic_values.side_effect = lambda name, *_: (
        (False, float("nan"), float("nan")) if name == "b" else (True, 0.0, 0.0)
    )
    assert node._ready_motor_names() == {"a"}
    module.BodyControlNode._position_callback(
        node, SimpleNamespace(actuator_names=["b"], positions_degrees=[0.0])
    )
    module.actuator_actions.set_target_position.assert_not_called()
    module.motor_actions.set_axis_state.assert_not_called()


def test_position_publisher_keeps_roster_and_logs_conversion_failure_once(
    body_io, monkeypatch
):
    import math

    module, node, _ = body_io
    monkeypatch.setattr(
        module, "BodyKinematicState", lambda: SimpleNamespace(actuators=[])
    )
    monkeypatch.setattr(module, "ActuatorKinematicState", SimpleNamespace)
    node.get_clock = lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(to_msg=lambda: "stamp")
    )
    node.position_state_publisher = Mock()
    module.kinematic_values.side_effect = lambda name, *_: (
        (False, math.nan, math.nan) if name == "b" else (True, 12.0, 3.0)
    )
    for _ in range(2):
        module.BodyControlNode._publish_position_state(node)
    message = node.position_state_publisher.publish.call_args.args[0]
    assert [a.actuator_name for a in message.actuators] == ["a", "b"]
    assert message.actuators[0].valid and message.actuators[0].position_degrees == 12.0
    assert not message.actuators[1].valid and math.isnan(
        message.actuators[1].position_degrees
    )
    assert math.isnan(message.actuators[1].velocity_degrees_per_second)
    node.get_logger().error.assert_called_once()
    assert '"b"' in node.get_logger().error.call_args.args[0]
    module.kinematic_values.side_effect = None
    module.kinematic_values.return_value = (True, 0.0, 0.0)
    module.BodyControlNode._publish_position_state(node)
    assert all(
        a.valid
        for a in node.position_state_publisher.publish.call_args.args[0].actuators
    )


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


def test_explicit_move_allows_idle_axes_but_policy_stream_cannot_auto_arm(body_io):
    module, node, _ = body_io
    move = SimpleNamespace(actuator_names=["a"], positions_degrees=[10.0])
    module.BodyControlNode._position_callback(node, move)
    module.actuator_actions.set_target_position.assert_not_called()
    module.BodyControlNode._position_callback(node, move, auto_arm=True)
    module.actuator_actions.set_target_position.assert_called_once_with(
        "a", 10.0, auto_arm=True
    )
    module.actuator_actions.configure_trajectory.assert_not_called()
    module.motor_actions.hold_current_position.assert_not_called()


@pytest.mark.parametrize(
    "invalid", ["bounds", "heartbeat", "encoder", "busy", "axis", "nan"]
)
def test_explicit_move_validates_the_whole_batch_before_any_io(body_io, invalid):
    module, node, states = body_io
    values = [1.0, 2.0]
    if invalid == "bounds":
        module.actuator_actions.validate_target_position.side_effect = [
            1.0,
            ValueError("bounds"),
        ]
    elif invalid == "heartbeat":
        states["b"].last_heartbeat_time = 0.0
    elif invalid == "encoder":
        states["b"].last_encoder_estimate_time = 0.0
    elif invalid == "busy":
        states["b"].current_state = module.MotorState.HOMING
    elif invalid == "axis":
        states["b"].axis_error = 1
    else:
        values[1] = float("nan")
    module.BodyControlNode._position_callback(
        node,
        SimpleNamespace(actuator_names=["a", "b"], positions_degrees=values),
        auto_arm=True,
    )
    module.actuator_actions.set_target_position.assert_not_called()
    module.motor_actions.set_axis_state.assert_not_called()


def test_emergency_latch_blocks_queued_moves_and_arm_until_idle_recovery(body_io):
    module, node, states = body_io
    assert command(body_io, "emergency").success
    assert node.motion_inhibited
    for state in (8, 11, 3):
        assert not command(body_io, "state", state=state).success
    move = SimpleNamespace(actuator_names=["a"], positions_degrees=[10.0])
    module.BodyControlNode._position_callback(node, move, auto_arm=True)
    module.actuator_actions.set_target_position.assert_not_called()
    assert command(body_io, "clear_errors").success
    assert node.motion_inhibited
    states["b"].current_state = module.MotorState.CLOSED_LOOP_CONTROL
    assert not command(body_io, "recover").success
    assert node.motion_inhibited
    states["b"].current_state = module.MotorState.IDLE
    states["b"].last_heartbeat_time = 0.0
    assert not command(body_io, "recover").success
    assert node.motion_inhibited
    states["b"].last_heartbeat_time = 10.0
    assert command(body_io, "recover").success
    assert not node.motion_inhibited
    # Recovery never arms; a new explicit move is still needed.
    assert all(
        call.args[1] == module.MotorState.IDLE
        for call in module.motor_actions.set_axis_state.call_args_list
    )
    module.BodyControlNode._position_callback(node, move, auto_arm=True)
    module.actuator_actions.set_target_position.assert_called_once()


@pytest.mark.parametrize("operation", ["emergency", "fault_stop", "recover"])
def test_partial_emergency_or_recovery_cannot_change_the_global_latch(
    body_io, operation
):
    module, node, _ = body_io
    assert not command(body_io, operation, names=["a"]).success
    assert not node.motion_inhibited
    node.motion_inhibited = True
    assert not command(body_io, "recover", names=["a"]).success
    assert node.motion_inhibited
    module.motor_actions.set_axis_state.assert_not_called()


@pytest.mark.parametrize(
    "problem", ["fault", "heartbeat", "encoder", "homing", "calibrating"]
)
def test_actuator_fault_stop_preserves_healthy_closed_loop_and_blocks_motion(
    body_io, problem
):
    module, node, states = body_io
    for motor in states.values():
        motor.current_state = module.MotorState.CLOSED_LOOP_CONTROL
    if problem == "fault":
        states["b"].encoder_error = 256
    elif problem == "heartbeat":
        states["b"].last_heartbeat_time = 0.0
    elif problem == "encoder":
        states["b"].last_encoder_estimate_time = 0.0
    else:
        states["b"].current_state = (
            module.MotorState.HOMING
            if problem == "homing"
            else module.MotorState.FULL_CALIBRATION_SEQUENCE
        )
    assert command(body_io, "fault_stop").success
    assert node.motion_inhibited
    module.motor_actions.hold_after_fault.assert_called_once_with("a")
    module.motor_actions.set_axis_state.assert_called_once_with(
        "b", module.MotorState.IDLE
    )
    assert not command(body_io, "state", ["a"], 8).success
    module.BodyControlNode._position_callback(
        node,
        SimpleNamespace(actuator_names=["a"], positions_degrees=[10.0]),
        auto_arm=True,
    )
    module.actuator_actions.set_target_position.assert_not_called()


def test_fault_recovery_keeps_healthy_axes_armed_and_requires_fault_clear(body_io):
    module, node, states = body_io
    states["a"].current_state = module.MotorState.CLOSED_LOOP_CONTROL
    states["b"].encoder_error = 256
    assert command(body_io, "fault_stop").success
    assert not command(body_io, "recover").success
    assert node.motion_inhibited
    states["b"].encoder_error = 0
    module.motor_actions.set_axis_state.reset_mock()
    module.motor_actions.hold_after_fault.reset_mock()
    assert command(body_io, "recover").success
    assert not node.motion_inhibited
    module.motor_actions.set_axis_state.assert_not_called()
    module.motor_actions.hold_after_fault.assert_not_called()


def test_failed_hold_idles_only_affected_axis_and_attempts_other_holds(body_io):
    module, _, states = body_io
    for motor in states.values():
        motor.current_state = module.MotorState.CLOSED_LOOP_CONTROL
    module.motor_actions.hold_after_fault.side_effect = [False, True]
    result = command(body_io, "fault_stop")
    assert not result.success and "a" in result.message
    assert module.motor_actions.hold_after_fault.call_args_list == [
        call("a"),
        call("b"),
    ]
    module.motor_actions.set_axis_state.assert_called_once_with(
        "a", module.MotorState.IDLE
    )


def test_explicit_estop_overrides_fault_stop_and_cannot_be_downgraded(body_io):
    module, node, states = body_io
    states["a"].current_state = module.MotorState.CLOSED_LOOP_CONTROL
    assert command(body_io, "fault_stop").success
    assert command(body_io, "emergency").success
    module.motor_actions.set_axis_state.reset_mock()
    module.motor_actions.hold_after_fault.reset_mock()
    assert command(body_io, "fault_stop").success
    assert node.emergency_disarm
    module.motor_actions.hold_after_fault.assert_not_called()
    assert module.motor_actions.set_axis_state.call_args_list == [
        call("a", module.MotorState.IDLE),
        call("b", module.MotorState.IDLE),
    ]
    assert not command(body_io, "recover").success


def test_failed_explicit_move_disarms_the_selected_batch(body_io):
    module, node, _ = body_io
    module.actuator_actions.set_target_position.side_effect = [True, False]
    module.BodyControlNode._position_callback(
        node,
        SimpleNamespace(actuator_names=["a", "b"], positions_degrees=[1.0, 2.0]),
        auto_arm=True,
    )
    assert module.motor_actions.set_axis_state.call_args_list == [
        call("a", module.MotorState.IDLE),
        call("b", module.MotorState.IDLE),
    ]


@pytest.mark.parametrize("exit_kind", ["SIGINT", "SIGTERM", "external_shutdown"])
def test_main_disarms_and_closes_can_before_context_shutdown(
    body_io, monkeypatch, exit_kind
):
    module, node, _ = body_io
    body_type = module.BodyControlNode
    events = []
    context = {"ok": True}
    node.destroy_node = lambda: events.append("destroy")
    node.shutdown_hardware = lambda: body_type.shutdown_hardware(node)
    monkeypatch.setattr(module, "BodyControlNode", lambda: node)
    monkeypatch.setattr(
        module.motor_actions,
        "set_axis_state",
        lambda name, state: events.append(("idle", name, state, context["ok"])),
    )
    monkeypatch.setattr(module.can_actions, "get_names", lambda: ("can0",))
    monkeypatch.setattr(
        module.can_actions, "close", lambda name: events.append(("close", name))
    )
    monkeypatch.setattr(module.rclpy, "init", Mock(), raising=False)

    def spin(_):
        if exit_kind == "external_shutdown":
            context["ok"] = False
            raise module.ExternalShutdownException()
        module.signal.raise_signal(getattr(module.signal, exit_kind))

    def shutdown():
        assert events[-1] == "destroy"
        events.append("context_shutdown")
        context["ok"] = False

    monkeypatch.setattr(module.rclpy, "spin", spin, raising=False)
    monkeypatch.setattr(module.rclpy, "try_shutdown", shutdown, raising=False)
    previous = {
        sig: module.signal.getsignal(sig)
        for sig in (module.signal.SIGINT, module.signal.SIGTERM)
    }
    module.main()
    was_live = exit_kind != "external_shutdown"
    assert events == [
        ("idle", "a", module.MotorState.IDLE, was_live),
        ("idle", "b", module.MotorState.IDLE, was_live),
        ("close", "can0"),
        "destroy",
        "context_shutdown",
    ]
    assert {sig: module.signal.getsignal(sig) for sig in previous} == previous
    module.rclpy.init.assert_called_once_with(
        args=None, signal_handler_options=module.SignalHandlerOptions.NO
    )
