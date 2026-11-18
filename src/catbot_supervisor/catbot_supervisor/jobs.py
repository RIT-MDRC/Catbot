"""Orin-owned allowlisted processes, with bounded nonblocking group cleanup."""

import os
import signal
import subprocess


class Jobs:
    def __init__(self, commands):
        for name, command in commands.items():
            if (
                not name
                or not isinstance(command, list)
                or not command
                or any(not isinstance(v, str) or not v or "\0" in v for v in command)
            ):
                raise ValueError("Jobs require names and nonempty argv lists")
        self.commands = commands
        self.children = {}
        self.stopping = {}

    def start(self, name):
        if name not in self.commands:
            raise ValueError("Unknown Orin job")
        if name in self.stopping:
            raise ValueError("Job is still stopping")
        child = self.children.get(name)
        if child is not None:
            if child.poll() is None:
                return
            # Even a reaped leader can leave descendants in its process group.
            self.stop(name, 0.0)
            raise ValueError("Exited job cleanup pending; retry after cleanup")
        self.children[name] = subprocess.Popen(
            self.commands[name], start_new_session=True, stdin=subprocess.DEVNULL
        )

    def stop(self, name, now):
        if name not in self.commands:
            raise ValueError("Unknown Orin job")
        child = self.children.get(name)
        if child is not None and name not in self.stopping:
            self._signal(child, signal.SIGINT)
            self.stopping[name] = (now + 3.0, 0)

    @staticmethod
    def _signal(child, sig):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            pass

    def running(self, name):
        child = self.children.get(name)
        return child is not None and child.poll() is None and name not in self.stopping

    def tick(self, now):
        for name, child in list(self.children.items()):
            if name not in self.stopping and child.poll() is not None:
                self.stop(name, now)
            stopping = self.stopping.get(name)
            if stopping is None:
                continue
            deadline, stage = stopping
            if now < deadline:
                continue
            self._signal(child, signal.SIGTERM if stage == 0 else signal.SIGKILL)
            if stage == 0:
                self.stopping[name] = (now + 2.0, 1)
            elif child.poll() is not None:
                del self.children[name]
                del self.stopping[name]

    def close(self):
        for child in self.children.values():
            self._signal(child, signal.SIGKILL)
            child.wait(timeout=3)
        self.children.clear()
        self.stopping.clear()
