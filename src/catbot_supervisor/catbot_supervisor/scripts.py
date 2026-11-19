"""Extensible nonblocking scripts; hardware effects go through Foundation I/O."""

from dataclasses import dataclass
from importlib.metadata import entry_points


@dataclass(frozen=True)
class Step:
    kind: str
    operation: str = ""
    names: tuple[str, ...] = ()
    state: int = 0
    timeout: float = 3.0


def maintenance(names, state=None):
    steps = [
        Step("motor", "idle"),
        Step("wait_state", state=1),
        Step("motor", "clear_errors"),
        Step("wait_clear"),
    ]
    if state is not None:
        for name in names:
            steps += [
                Step("motor", "state", (name,), state),
                Step("wait_state", names=(name,), state=state),
                Step("wait_state", names=(name,), state=1, timeout=30.0),
            ]
    for name in names:
        steps += [
            Step("motor", "trajectory", (name,)),
            Step("motor", "hold", (name,)),
            Step("motor", "state", (name,), 8),
            Step("wait_ready", names=(name,)),
        ]
    return steps


def registry():
    scripts = {
        "startup": lambda names: (
            [
                Step("wait_health", timeout=5.0),
                Step("wait_policy_stopped", timeout=8.0),
                Step("wait_preflight", timeout=120.0),
                Step("job_start", "policy"),
                Step("wait_policy_ready", timeout=120.0),
                Step("wait_link", timeout=120.0),
            ]
            + maintenance(names, 4)
        ),
        "shutdown": lambda names: [
            Step("motor", "idle"),
            Step("wait_state", state=1),
            Step("job_stop", "policy"),
            Step("wait_policy_stopped", timeout=8.0),
        ],
        "restart_policy": lambda names: [
            Step("wait_health", timeout=5.0),
            Step("wait_preflight", timeout=120.0),
            Step("motor", "idle"),
            Step("wait_state", state=1),
            Step("job_restart", "policy", timeout=8.0),
            Step("wait_policy_ready", timeout=120.0),
            Step("wait_link", timeout=120.0),
            *maintenance(names),
        ],
        "emergency": lambda names: [Step("motor", "idle"), Step("wait_state", state=1)],
        "home": lambda names: maintenance(names, 11),
        "calibrate": lambda names: maintenance(names, 4),
        "full_calibrate": lambda names: maintenance(names, 3),
        "clear_errors": lambda names: maintenance(names),
    }
    for plugin in entry_points(group="catbot_supervisor.scripts"):
        if plugin.name in scripts:
            raise ValueError(f"Script already registered: {plugin.name}")
        scripts[plugin.name] = plugin.load()
    return scripts


class ScriptRunner:
    """One step per tick; emergency replacement never waits for an old future."""

    def __init__(self, dispatch, satisfied):
        self.dispatch, self.satisfied = dispatch, satisfied
        self.steps = []
        self.index = 0
        self.deadline = None
        self.future = None
        self.error = ""

    @property
    def active(self):
        return self.index < len(self.steps) and not self.error

    def start(self, steps):
        self.steps, self.index = list(steps), 0
        self.deadline = self.future = None
        self.error = ""

    def tick(self, now):
        if not self.active:
            return
        step = self.steps[self.index]
        try:
            if self.deadline is None:
                self.deadline = now + step.timeout
            if now >= self.deadline:
                raise RuntimeError(
                    f"Script step timed out: {step.kind} {step.operation}"
                )
            if not step.kind.startswith("wait_") and self.future is None:
                self.future = self.dispatch(step)
            done = (
                self.satisfied(step)
                if step.kind.startswith("wait_")
                else self.future is not None and self.future.done()
            )
            if not done:
                return
            if self.future is not None:
                result = self.future.result()
                if result is None or not result.success:
                    raise RuntimeError(getattr(result, "message", "service failed"))
            self.index += 1
            self.deadline = self.future = None
        except (RuntimeError, ValueError, OSError, KeyError) as error:
            self.error = str(error)
