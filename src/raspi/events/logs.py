from events.event_types import EventType
from datetime import datetime

LOG_FILE_PATH = "log.json"  # change as needed

class LogEntry():
    event_type : EventType
    data : object
    timestamp : datetime

def log_event(entry : LogEntry) -> None:
    ...