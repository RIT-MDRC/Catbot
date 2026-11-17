import copy
import json
from pathlib import Path

import pytest
import torch
from catbot_policy.runtime import finite_tensor, validate_metadata
from hypothesis import given
from hypothesis import strategies as st

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[3] / "tests/fixtures/contract.json").read_text()
)
INVALID = st.one_of(
    st.booleans(), st.sampled_from([float("nan"), float("inf"), -float("inf")])
)


def test_cross_version_loading_retains_contract_validation():
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = "0.0.0"
    with pytest.raises(ValueError, match="must match"):
        validate_metadata(metadata)
    with pytest.warns(RuntimeWarning, match="not numerical parity"):
        validate_metadata(metadata, torch_compatibility="load")
    metadata["policy_contract"]["observation_dimension"] = 89
    with (
        pytest.warns(RuntimeWarning),
        pytest.raises(ValueError, match="observation/action contract"),
    ):
        validate_metadata(metadata, torch_compatibility="load")


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("torch_version", "", "PyTorch version"),
        ("torch_version", None, "PyTorch version"),
        ("model_sha256", "0" * 63, "model_sha256"),
        ("policy_sha256", "z" * 64, "policy_sha256"),
    ],
)
def test_metadata_rejects_invalid_versions_and_checksums(key, value, message):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    metadata[key] = value
    with pytest.raises(ValueError, match=message):
        validate_metadata(metadata)


def test_unknown_torch_compatibility_is_rejected():
    with pytest.raises(ValueError, match="exact or load"):
        validate_metadata(FIXTURE["metadata"], torch_compatibility="ignore")


@pytest.mark.parametrize("ranges", [[], [[-1, 1]] * 11, None])
def test_metadata_requires_all_twelve_control_ranges(ranges):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    metadata["policy_contract"]["control_ranges"] = ranges
    with pytest.raises(ValueError, match="12 actuator control ranges"):
        validate_metadata(metadata)


def test_boolean_tensor_requires_explicit_permission():
    values = torch.tensor([True, False])
    with pytest.raises(ValueError, match="Invalid boolean"):
        finite_tensor(values, 2, "contact")
    torch.testing.assert_close(
        finite_tensor(values, 2, "contact", allow_bool=True), torch.tensor([1.0, 0.0])
    )


@given(st.integers(0, 11), INVALID)
def test_finite_tensor_rejects_invalid_member(index, invalid):
    values = [0.0] * 12
    values[index] = invalid
    with pytest.raises(ValueError):
        finite_tensor(values, 12, "test")


@given(
    st.lists(
        st.floats(allow_nan=False, allow_infinity=False, width=32), max_size=24
    ).filter(lambda x: len(x) != 12)
)
def test_finite_tensor_rejects_wrong_length(values):
    with pytest.raises(ValueError):
        finite_tensor(values, 12, "test")


@given(
    st.integers(0, 11),
    st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.01, max_value=10, allow_nan=False, allow_infinity=False),
)
def test_metadata_rejects_inverted_ranges(index, lo, delta):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    metadata["policy_contract"]["control_ranges"][index] = [lo + delta, lo]
    with pytest.raises(ValueError, match="ordered"):
        validate_metadata(metadata)


@given(
    st.sampled_from(
        [
            "action_smoothing",
            "trot_speed",
            "bound_speed",
            "gait_transition_seconds",
            "air_time_limit",
        ]
    ),
    INVALID,
)
def test_metadata_rejects_invalid_settings(name, invalid):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    metadata["settings"][name] = invalid
    with pytest.raises(ValueError):
        validate_metadata(metadata)


@given(st.integers(0, 11), INVALID)
def test_metadata_rejects_invalid_bounds(index, invalid):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    metadata["policy_contract"]["control_ranges"][index][0] = invalid
    with pytest.raises(ValueError):
        validate_metadata(metadata)


@given(
    st.sampled_from(
        [
            "schema_version",
            "torch_version",
            "policy_contract",
            "settings",
            "model_sha256",
            "policy_sha256",
        ]
    )
)
def test_missing_metadata_is_value_error(key):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    del metadata[key]
    with pytest.raises(ValueError):
        validate_metadata(metadata)


@given(st.integers(min_value=1, max_value=1000))
def test_float32_overflow_rejected(exponent):
    with pytest.raises(ValueError):
        finite_tensor([10 ** (40 + exponent)], 1, "overflow")


@pytest.mark.parametrize(
    "path", [("schema_version",), ("policy_contract", "observations", 11, "size")]
)
def test_boolean_cannot_alias_integer_metadata(path):
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    parent = metadata
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = True
    with pytest.raises(ValueError):
        validate_metadata(metadata)


@given(st.floats(min_value=0.1, max_value=10, allow_nan=False, allow_infinity=False))
def test_inverted_range_cannot_round_to_valid_float32(value):
    import math

    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["torch_version"] = torch.__version__.split("+")[0]
    metadata["policy_contract"]["control_ranges"][0] = [
        math.nextafter(value, math.inf),
        value,
    ]
    with pytest.raises(ValueError, match="ordered"):
        validate_metadata(metadata)


@given(
    st.sampled_from(["signs", "offsets_degrees", "minimum_degrees", "maximum_degrees"]),
    st.integers(0, 11),
    INVALID,
)
def test_shared_mapping_rejects_invalid_numbers(field, index, invalid):
    from catbot_policy.configuration import validate_mapping

    mapping = copy.deepcopy(FIXTURE["mapping"])
    mapping[field][index] = invalid
    with pytest.raises(ValueError):
        validate_mapping(mapping)
