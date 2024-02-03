from events.event_types import EventType
from datetime import datetime

LOG_FILE_PATH = "log.json"  # change as needed

class LogEntry():
    event_type : EventType
    data : object
    timestamp : datetime

def log_event(entry : LogEntry) -> None:
    """
    Log the given event and its related info to a file.

    :param entry: information about an event at a specific time
    """
    ...