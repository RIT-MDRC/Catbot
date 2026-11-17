"""Selection and CLI failures must be useful without contacting W&B."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from catbot_policy.deployment import RUN_FILES, main, select_run
from test_deployment import FakeApi, FakeFile, FakeRun


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ([], "Specify RUN_ID"),
        (["run1", "--run-id", "run2"], "either positional run"),
        (["run1", "1", "--checkpoint", "2"], "either positional checkpoint"),
        (["run1", "--latest"], "Choose an explicit run"),
        (["--latest", "--checkpoint", "1"], "requires an explicit run"),
    ],
)
def test_conflicting_cli_selection_fails_before_api_access(
    arguments, message, monkeypatch, capsys
):
    api = Mock()
    monkeypatch.setitem(sys.modules, "wandb", SimpleNamespace(Api=api))
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2
    assert message in capsys.readouterr().err
    api.assert_not_called()


def test_cli_named_selection_normalizes_checkpoint_and_logs_in(
    tmp_path, monkeypatch, capsys
):
    api, login = Mock(), Mock()
    monkeypatch.setitem(
        sys.modules,
        "wandb",
        SimpleNamespace(Api=lambda: api, login=login, Error=RuntimeError),
    )
    bundle = tmp_path / "bundle"
    prepare = Mock(return_value=bundle)
    monkeypatch.setattr("catbot_policy.deployment.prepare_policy", prepare)
    main(
        [
            "--run-id",
            "run1",
            "--checkpoint",
            "100",
            "--entity",
            "team",
            "--project",
            "catbot",
            "--directory",
            str(tmp_path),
            "--login",
        ]
    )
    login.assert_called_once_with()
    prepare.assert_called_once_with(
        api,
        run_path="team/catbot/run1",
        entity="team",
        project="catbot",
        checkpoint="model_100.pt",
        directory=tmp_path,
    )
    assert f"policy_bundle: {bundle}" in capsys.readouterr().out


def test_cli_preparation_error_reports_cache_and_returns_failure(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setitem(
        sys.modules, "wandb", SimpleNamespace(Api=Mock(), Error=RuntimeError)
    )
    monkeypatch.setattr(
        "catbot_policy.deployment.prepare_policy",
        Mock(side_effect=OSError("download interrupted")),
    )
    with pytest.raises(SystemExit) as error:
        main(["run1", "--directory", str(tmp_path)])
    assert error.value.code == 1
    message = capsys.readouterr().err
    assert "Policy preparation failed: download interrupted" in message
    assert "Downloaded models:\n  (none)" in message


@pytest.mark.parametrize("entity", [None, "../team", 42])
def test_auto_selection_requires_valid_entity(entity):
    api = FakeApi([])
    api.default_entity = entity
    with pytest.raises(ValueError, match="WANDB_ENTITY"):
        select_run(api, None, None, "catbot", None)
    assert api.request is None


def test_auto_selection_reports_no_complete_runs():
    with pytest.raises(ValueError, match="No complete training runs"):
        select_run(FakeApi([]), None, "team", "catbot", None)


def test_explicit_run_requires_a_checkpoint(tmp_path):
    api = FakeApi([FakeRun([FakeFile(tmp_path / name) for name in RUN_FILES])])
    with pytest.raises(ValueError, match="no model_N.pt checkpoints"):
        select_run(api, "team/catbot/run1", None, "catbot", None)
