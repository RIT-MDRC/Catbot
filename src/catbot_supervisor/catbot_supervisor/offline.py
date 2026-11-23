"""Idle-only FIFO for allowlisted offline processes; no shell interpretation."""

from collections import deque

from catbot_supervisor.jobs import Jobs


class OfflineQueue:
    def __init__(self, commands, *, max_pending=16):
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self.jobs = Jobs(commands)
        self.pending = deque()
        self.active = None
        self.max_pending = max_pending

    def enqueue(self, name):
        self.jobs._known(name)
        if name == self.active or name in self.pending:
            return
        if len(self.pending) >= self.max_pending:
            raise ValueError("offline queue full")
        self.pending.append(name)

    def cancel(self, name, now):
        self.jobs._known(name)
        self.pending = deque(value for value in self.pending if value != name)
        self.jobs.stop(name, now)

    def tick(self, now, *, idle):
        if not idle:
            self.pending.clear()
            for name in self.jobs.children:
                self.jobs.stop(name, now)
        self.jobs.tick(now)
        if self.active not in self.jobs.children:
            self.active = None
        if idle and self.active is None and not self.jobs.children and self.pending:
            name = self.pending.popleft()
            try:
                self.jobs.start(name, now)
                self.active = name
            except OSError as error:
                self.jobs.errors[name] = str(error)

    def status(self):
        return {
            "pending": list(self.pending),
            "active": self.active,
            "jobs": self.jobs.status(),
        }

    def close(self):
        self.pending.clear()
        self.jobs.close()
