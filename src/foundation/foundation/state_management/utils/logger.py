import logging
from datetime import datetime as d
from pathlib import Path
import re

import __main__

LOG_LEVEL = {
    "Debug": logging.DEBUG,
    "Info": logging.INFO,
    "Warning": logging.WARNING,
    "Error": logging.ERROR,
    "Critical": logging.CRITICAL,
}


def map_level(level: str) -> int:
    """
    Maps the level string to the corresponding logging level.

    :param level: the level string
    :return: the logging level
    """
    return LOG_LEVEL.get(level, logging.DEBUG)


def set_log_event_function(callback: callable):
    """Set a callback function to be called when a log is done. The callback function must accept logRecord as the first argument and return True to be recorded or False to be ignored.
    Although it is not an intended way to use this as a event handler it is a simple and effective way to use it.

    Args:
        callback (callable): function to be called when a log is done
    """
    logging.root.addFilter(callback)


def configure_logger(level: str = "Debug"):
    """
    Configure the logger.

    Keep the latest five runs for this program, including the current run.

    :param level: the level to log at
    """
    lvl = map_level(level)
    print(f"Configuring logger {level}...")
    start_time = d.now().strftime("%Y-%m-%d.%H:%M:%S.%f")
    filename = "foundation." + __main__.__file__.split("/")[-1].split(".")[0]
    log_dir = Path(".log")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{start_time}.{filename}.{level}.log"
    logging.basicConfig(
        filename=log_path,
        format="foundation:%(filename)s: %(message)s",
        level=lvl,  # TODO: hook it to env or config file
        force=True,
    )
    pattern = re.compile(
        rf"\d{{4}}-\d{{2}}-\d{{2}}\.\d{{2}}:\d{{2}}:\d{{2}}(?:\.\d{{6}})?\.{re.escape(filename)}\.(?:Debug|Info|Warning|Error|Critical)\.log"
    )
    logs = sorted(
        path
        for path in log_dir.iterdir()
        if path.is_file() and not path.is_symlink() and pattern.fullmatch(path.name)
    )
    for old_log in logs[:-5]:
        old_log.unlink(missing_ok=True)
