import pytest
from catbot_supervisor.heartbeat_recovery import HeartbeatRecovery


@pytest.mark.parametrize(
    "reason",
    [
        "Foundation actuator heartbeat unavailable: frk",
        "Orin heartbeat lost",
        "Link or Foundation lost during script: Orin heartbeat lost",
    ],
)
def test_recovery_requires_stable_healthy_feedback_and_only_fires_once(reason):
    recovery = HeartbeatRecovery()
    recovery.start(reason)
    assert not recovery.ready(0, False)
    assert not recovery.ready(1, True)
    assert not recovery.ready(1.9, True)
    assert not recovery.ready(2, False)
    assert not recovery.ready(3, True)
    assert recovery.ready(4, True)
    assert not recovery.ready(5, True)


@pytest.mark.parametrize(
    "reason",
    [
        "operator emergency",
        "Foundation actuator fault: frk",
        "Script step timed out: wait_clear",
        "Orin reported degraded: policy action stream unavailable",
    ],
)
def test_other_emergencies_never_auto_recover_and_cancel_pending_recovery(reason):
    recovery = HeartbeatRecovery()
    recovery.start("Orin heartbeat lost")
    recovery.ready(0, True)
    recovery.start(reason)
    assert not recovery.ready(1, True)
    assert not recovery.ready(10, True)


def test_motor_fault_cancels_automatic_recovery_even_if_it_later_clears():
    recovery = HeartbeatRecovery()
    recovery.start("Orin heartbeat lost")
    assert not recovery.ready(0, True, faulted=True)
    assert not recovery.ready(10, True)


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_invalid_stability_period_is_rejected(seconds):
    with pytest.raises(ValueError):
        HeartbeatRecovery(seconds)
