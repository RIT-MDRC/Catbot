import json
from pathlib import Path

import torch
from catbot_policy.protocol import OBSERVATION_FIELDS
from catbot_policy.runtime import ActuatorMapping, PolicyRuntime
from test_runtime import make_bundle


def test_golden_observation_and_mapping(tmp_path):
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[3] / "tests/fixtures/contract.json"
        ).read_text()
    )
    assert [list(x) for x in OBSERVATION_FIELDS] == fixture["layout"]
    runtime = PolicyRuntime(make_bundle(tmp_path))
    runtime.update_feedback(fixture["feedback"], 0)
    runtime.set_command(fixture["local"]["command"])
    runtime.previous_action.copy_(torch.tensor(fixture["local"]["previous_action"]))
    runtime.previous_action_delta.copy_(
        torch.tensor(fixture["local"]["previous_action_delta"])
    )
    runtime.gait_phase, runtime.gait_blend = 0.25, 0.4
    torch.testing.assert_close(
        runtime.observation()[0],
        torch.tensor(fixture["observation"]),
        atol=1e-6,
        rtol=1e-6,
    )
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(fixture["mapping"]))
    actual = ActuatorMapping(path).convert(torch.tensor(fixture["radians"]))
    torch.testing.assert_close(torch.tensor(actual), torch.tensor(fixture["degrees"]))
