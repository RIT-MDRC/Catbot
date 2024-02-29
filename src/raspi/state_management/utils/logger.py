import logging
from datetime import datetime as d

level_config = {
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
    return level_config.get(level, logging.DEBUG)


def configure_logger(level: str = "Debug"):
    """
    Configure the logger.

    :param level: the level to log at
    """
    start_time = d.now().strftime("%Y-%m-%d.%H:%M:%S")
    logging.basicConfig(
        filename=f".log/{start_time}.debug.log",
        format="%(filename)s: %(message)s",
        level=map_level(level),  # TODO: hook it to env or config file
    )
