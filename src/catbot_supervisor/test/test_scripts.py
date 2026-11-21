from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from catbot_supervisor.scripts import (
    ScriptRunner,
    Step,
    arm_steps,
    maintenance,
    registry,
)


def test_arm_only_requests_closed_loop_and_waits_for_readiness():
    assert arm_steps(("flf", "frf")) == [
        Step("motor", "state", ("flf",), 8),
        Step("wait_ready", names=("flf",)),
        Step("motor", "state", ("frf",), 8),
        Step("wait_ready", names=("frf",)),
    ]


@pytest.mark.parametrize(
    "name",
    [
        "startup",
        "restart_policy",
        "home",
        "home_robot",
        "calibrate",
        "full_calibrate",
        "clear_errors",
        "sample_home",
        "sample_calibrate",
    ],
)
def test_builtin_arming_never_reconfigures_or_overwrites_motor_targets(name):
    names = tuple(
        f"{leg}{joint}" for leg in ("fl", "fr", "bl", "br") for joint in ("a", "f", "k")
    )
    steps = registry()[name](names)
    assert any(s.kind == "motor" and s.state == 8 for s in steps)
    assert not any(
        s.kind == "motor" and s.operation in ("trajectory", "hold") for s in steps
    )


def test_runner_waits_for_service_and_confirmation_then_advances():
    future = Future()
    finished = Future()
    finished.set_result(SimpleNamespace(success=True))
    dispatch = Mock(side_effect=[None, future, finished])
    satisfied = Mock(return_value=False)
    idle, wait, hold = (
        Step("motor", "idle"),
        Step("wait_state", state=1),
        Step("motor", "hold"),
    )
    runner = ScriptRunner(dispatch, satisfied)
    runner.start([idle, wait, hold])
    runner.tick(0)
    runner.tick(0.1)
    runner.tick(0.15)
    assert dispatch.call_args_list == [call(idle), call(idle)]
    satisfied.assert_not_called()
    future.set_result(SimpleNamespace(success=True))
    runner.tick(0.2)
    runner.tick(0.3)
    satisfied.assert_called_once_with(wait)
    assert dispatch.call_count == 2
    assert runner.active
    satisfied.return_value = True
    runner.tick(0.4)
    runner.tick(0.5)
    assert dispatch.call_args_list == [call(idle), call(idle), call(hold)]
    assert not runner.active
    assert not runner.error


@pytest.mark.parametrize("kind", ["service", "wait"])
def test_script_timeouts_fail_instead_of_claiming_success(kind):
    dispatch = Mock(return_value=Future())
    runner = ScriptRunner(dispatch, lambda step: False)
    timed = Step("motor" if kind == "service" else "wait_state", timeout=1)
    runner.start([timed, Step("motor", "hold")])
    runner.tick(0)
    runner.tick(1)
    runner.tick(2)
    assert not runner.active
    assert "timed out" in runner.error
    assert dispatch.call_args_list == ([call(timed)] if kind == "service" else [])


@pytest.mark.parametrize("failure", ["response", "exception"])
def test_failed_service_never_dispatches_followup_work(failure):
    future = Future()
    if failure == "response":
        future.set_result(SimpleNamespace(success=False, message="CAN failed"))
    else:
        future.set_exception(OSError("CAN failed"))
    dispatch = Mock(return_value=future)
    runner = ScriptRunner(dispatch, lambda step: True)
    arm = Step("motor", "state", state=8)
    runner.start([arm, Step("motor", "hold")])
    runner.tick(0)
    runner.tick(0.1)
    assert not runner.active
    assert runner.error == "CAN failed"
    dispatch.assert_called_once_with(arm)


def test_emergency_dispatches_idle_without_waiting_for_pending_service():
    pending = Future()
    idle_result = Future()
    idle_result.set_result(SimpleNamespace(success=True))
    dispatch = Mock(side_effect=[pending, idle_result])
    runner = ScriptRunner(dispatch, lambda step: True)
    arm = Step("motor", "state", state=8)
    runner.start([arm, Step("motor", "hold")])
    runner.tick(1)
    assert not pending.done()
    runner.start(registry()["emergency"](("a",)))
    runner.tick(1.1)
    assert dispatch.call_args_list == [call(arm), call(Step("motor", "emergency"))]
    # A late reply from the replaced script must not resume its remaining work.
    pending.set_result(SimpleNamespace(success=True))
    runner.tick(1.2)
    runner.tick(1.3)
    assert dispatch.call_count == 2
    assert not runner.active
    assert not runner.error


def test_script_registry_and_axis_order_are_extensible(monkeypatch):
    monkeypatch.setattr(
        "catbot_supervisor.scripts.entry_points",
        lambda **kwargs: [
            SimpleNamespace(
                name="custom", load=lambda: lambda names: [Step("job_start", "record")]
            )
        ],
    )
    scripts = registry()
    assert scripts["custom"](())[0].operation == "record"
    steps = maintenance(("a", "b"), 4)
    assert steps[0].operation == "idle"
    calibration = [s for s in steps if s.operation == "state" and s.state == 4]
    assert [s.names for s in calibration] == [("a",), ("b",)]
    assert all(s.names for s in steps if s.operation == "state" and s.state == 8)
    assert scripts["emergency"](())[0].operation == "emergency"


def test_plugins_cannot_replace_emergency(monkeypatch):
    monkeypatch.setattr(
        "catbot_supervisor.scripts.entry_points",
        lambda **kwargs: [SimpleNamespace(name="emergency")],
    )
    with pytest.raises(ValueError):
        registry()


def test_operator_confirmation_is_specific_and_consumed_once():
    dispatch = Mock(return_value=Future())
    runner = ScriptRunner(dispatch, Mock())
    runner.start([Step("wait_operator", "Check clearance"), Step("motor", "hold")])
    with pytest.raises(ValueError):
        runner.respond("early", 0)
    runner.tick(0)
    token = runner.prompt["id"]
    runner.tick(0.1)
    dispatch.assert_not_called()
    with pytest.raises(ValueError):
        runner.respond("stale", 0.2)
    runner.respond(token, 0.2)
    with pytest.raises(ValueError):
        runner.respond(token, 0.3)
    runner.tick(0.3)
    dispatch.assert_called_once_with(Step("motor", "hold"))


def test_prompt_timeout_and_preemption_reject_old_confirmation():
    runner = ScriptRunner(Mock(), Mock())
    prompt = Step("wait_operator", "Check setup", timeout=1)
    runner.start([prompt])
    runner.tick(0)
    token = runner.prompt["id"]
    with pytest.raises(ValueError, match="expired"):
        runner.respond(token, 1)
    runner.tick(1)
    assert not runner.active
    assert runner.prompt is None
    runner.start([prompt])
    runner.tick(2)
    assert runner.prompt["id"] != token
    runner.start(registry()["emergency"](()))
    with pytest.raises(ValueError):
        runner.respond(token, 2.1)
    assert runner.prompt is None


@pytest.mark.parametrize("script,state", [("sample_home", 11), ("sample_calibrate", 4)])
def test_sample_requires_confirmation_before_each_axis_operation(script, state):
    steps = registry()[script](("a", "b"))
    operations = [
        i for i, s in enumerate(steps) if s.operation == "state" and s.state == state
    ]
    assert [steps[i].names for i in operations] == [("a",), ("b",)]
    assert all(steps[i - 1].kind == "wait_operator" for i in operations)
    assert len([s for s in steps if s.kind == "wait_operator"]) == 2


def test_buffer_waits_full_duration_without_dispatch_and_can_be_preempted():
    dispatch = Mock(return_value=Future())
    runner = ScriptRunner(dispatch, Mock())
    runner.start([Step("delay", timeout=15.0), Step("motor", "hold")])
    runner.tick(10)
    runner.tick(24.99)
    dispatch.assert_not_called()
    runner.tick(25)
    assert not runner.error
    runner.tick(25.01)
    dispatch.assert_called_once_with(Step("motor", "hold"))
    runner.start([Step("delay", timeout=15.0)])
    runner.tick(30)
    runner.start([Step("motor", "idle")])
    runner.tick(30.01)
    assert dispatch.call_args == call(Step("motor", "idle"))
