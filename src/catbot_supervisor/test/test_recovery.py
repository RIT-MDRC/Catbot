from types import SimpleNamespace

import pytest
from catbot_supervisor.homing import ERROR_FIELDS
from catbot_supervisor.recovery import endstop_axes


def state(axis_error=0, **updates):
    return SimpleNamespace(
        **{
            **dict.fromkeys(ERROR_FIELDS, 0),
            "axis_error_flags": axis_error,
            "axis_state": 1,
            "heartbeat_available": True,
            **updates,
        }
    )


def test_only_stopped_endstop_axes_are_selected():
    body = {"a": state(4096), "b": state(8192), "c": state(axis_state=8)}
    assert endstop_axes(body, tuple(body)) == ("a", "b")
    assert endstop_axes({"a": state()}, ("a",)) == ()


@pytest.mark.parametrize(
    "sample",
    [
        state(256),
        state(8192 | 256),
        state(8192, encoder_error_flags=128),
        state(8192, axis_state=8),
        state(heartbeat_available=False),
    ],
)
def test_unrelated_faults_missing_heartbeat_and_active_faulted_axes_block(sample):
    with pytest.raises(ValueError):
        endstop_axes({"a": sample}, ("a",))


def test_partial_roster_blocks_recovery():
    with pytest.raises(ValueError):
        endstop_axes({}, ("a",))
