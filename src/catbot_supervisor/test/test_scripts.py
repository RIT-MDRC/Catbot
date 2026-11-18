from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from catbot_supervisor.scripts import ScriptRunner, Step, maintenance, registry


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
    assert dispatch.call_args_list == [call(arm), call(Step("motor", "idle"))]
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
    assert scripts["emergency"](())[0].operation == "idle"


def test_plugins_cannot_replace_emergency(monkeypatch):
    monkeypatch.setattr(
        "catbot_supervisor.scripts.entry_points",
        lambda **kwargs: [SimpleNamespace(name="emergency")],
    )
    with pytest.raises(ValueError):
        registry()
