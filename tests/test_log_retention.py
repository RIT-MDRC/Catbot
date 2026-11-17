"""Run-log retention stays scoped to each program and preserves other files."""

import importlib.util
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "source,prefix",
    [
        ("src/foundation/foundation/state_management/utils/logger.py", "foundation"),
        ("src/ui/ui/utils/logger.py", "ui"),
    ],
)
def test_log_retention(tmp_path, monkeypatch, source, prefix):
    spec = importlib.util.spec_from_file_location("retention_logger", ROOT / source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module.__main__, "__file__", "demo.py")
    handlers = logging.root.handlers[:]
    # Isolate basicConfig(force=True) from pytest's own handlers.
    logging.root.handlers = []
    original_level = logging.root.level
    try:
        module.configure_logger()
        log_dir = tmp_path / ".log"
        unrelated = log_dir / "other.log"
        unrelated.touch()
        for day in range(1, 8):
            (log_dir / f"2025-03-{day:02d}.14:43:50.{prefix}.demo.Info.log").touch()
        module.configure_logger("Error")
        logs = sorted(log_dir.glob(f"*.{prefix}.demo.*.log"))
        assert len(logs) == 5
        assert not (log_dir / f"2025-03-01.14:43:50.{prefix}.demo.Info.log").exists()
        assert unrelated.exists()
        logging.error("current run still writable")
        assert any("current run still writable" in log.read_text() for log in logs)
    finally:
        for handler in logging.root.handlers:
            handler.close()
        logging.root.handlers = handlers
        logging.root.setLevel(original_level)
