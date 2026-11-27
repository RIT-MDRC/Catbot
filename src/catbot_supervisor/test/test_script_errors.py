from types import SimpleNamespace
from unittest.mock import Mock

from catbot_supervisor.homing import ERROR_FIELDS
from catbot_supervisor.script_errors import clear_timeout_reason
from catbot_supervisor.scripts import ScriptRunner, Step


def state(**updates):
    return SimpleNamespace(
        **{**dict.fromkeys(ERROR_FIELDS, 0), "heartbeat_available": True, **updates}
    )


def test_timeout_reports_only_blocking_axes_and_their_decoded_faults():
    body = {
        "bra": state(
            axis_error_flags=256,
            axis_error_messages=["ENCODER_FAILED"],
            encoder_error_flags=128,
            encoder_error_messages=["ABS_SPI_COM_FAIL"],
        ),
        "bla": state(),
        "frk": state(heartbeat_available=False),
    }
    describe = lambda step: clear_timeout_reason(body, step.names, step.timeout, True)
    dispatch = Mock()
    runner = ScriptRunner(dispatch, lambda step: False, describe)
    runner.start(
        [
            Step("wait_clear", names=tuple(body), timeout=3),
            Step("motor", "state", state=3),
        ]
    )
    runner.tick(0)
    runner.tick(3)
    assert "wait_clear (3 s)" in runner.error
    assert (
        "bra: axis=256 [ENCODER_FAILED], encoder=128 [ABS_SPI_COM_FAIL]" in runner.error
    )
    assert "frk: no fresh CAN heartbeat" in runner.error
    assert "bla:" not in runner.error
    assert not runner.active
    dispatch.assert_not_called()


def test_missing_stale_and_already_cleared_feedback_have_distinct_messages():
    assert "No fresh /body/state/error" in clear_timeout_reason({}, ("a",), 3, False)
    assert "a: missing motor status" in clear_timeout_reason({}, ("a",), 3, True)
    assert "latest report has no blocking axis faults" in clear_timeout_reason(
        {"a": state()}, ("a",), 3, True
    )


def test_undecoded_flags_keep_numeric_value_and_selection_is_respected():
    body = {"a": state(axis_error_flags=256), "b": state(axis_error_flags=8192)}
    message = clear_timeout_reason(body, ("a",), 3, True)
    assert "axis=256 [UNDECODED]" in message
    assert "b:" not in message
