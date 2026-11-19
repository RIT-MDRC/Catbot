"""Allowlisted process groups with asynchronous, coalesced start/stop/restart."""

import os
import signal
import subprocess
import time


class Jobs:
    def __init__(self, commands, before_start=None):
        for name, command in commands.items():
            if (
                not name
                or not isinstance(command, list)
                or not command
                or any(not isinstance(v, str) or not v or "\0" in v for v in command)
            ):
                raise ValueError("Jobs require names and nonempty argv lists")
        self.commands = commands
        self.before_start = before_start
        self.children, self.stopping, self.pending = {}, {}, set()
        self.exits, self.errors = {}, {}

    def _known(self, name):
        if name not in self.commands:
            raise ValueError("Unknown Orin job")

    def _spawn(self, name):
        if self.before_start is not None:
            self.before_start(name)
        self.children[name] = subprocess.Popen(
            self.commands[name], start_new_session=True, stdin=subprocess.DEVNULL
        )
        self.pending.discard(name)
        self.errors.pop(name, None)
        self.exits.pop(name, None)

    def start(self, name, now=None):
        self._known(name)
        if self.running(name):
            return
        if name in self.children:
            self.pending.add(name)
            self.stop(
                name, time.monotonic() if now is None else now, cancel_pending=False
            )
        else:
            self._spawn(name)

    def restart(self, name, now):
        self._known(name)
        if name in self.pending:
            return
        if name not in self.children:
            self._spawn(name)
        else:
            self.pending.add(name)
            self.stop(name, now, cancel_pending=False)

    def stop(self, name, now, cancel_pending=True):
        self._known(name)
        if cancel_pending:
            self.pending.discard(name)
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
                self.exits[name] = child.returncode
                self.errors[name] = f"job exited ({child.returncode})"
                self.stop(name, now, cancel_pending=False)
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
                self.exits[name] = child.returncode
                del self.children[name]
                del self.stopping[name]
        for name in list(self.pending):
            if name not in self.children:
                try:
                    self._spawn(name)
                except (ValueError, OSError) as error:
                    self.pending.discard(name)
                    self.errors[name] = str(error)

    def status(self, name=""):
        names = [name] if name else list(self.commands)
        for value in names:
            self._known(value)
        return {
            value: {
                "state": "restarting"
                if value in self.pending
                else "stopping"
                if value in self.stopping
                else "running"
                if self.running(value)
                else "failed"
                if value in self.errors
                else "stopped",
                "pid": self.children[value].pid if value in self.children else None,
                "exit_code": self.exits.get(value),
                "error": self.errors.get(value, ""),
            }
            for value in names
        }

    def close(self):
        self.pending.clear()
        for child in self.children.values():
            self._signal(child, signal.SIGKILL)
            child.wait(timeout=3)
        self.children.clear()
        self.stopping.clear()
