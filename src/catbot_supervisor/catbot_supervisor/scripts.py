"""Extensible nonblocking scripts; hardware effects go through Foundation I/O."""

from dataclasses import dataclass
from importlib.metadata import entry_points
from uuid import uuid4


@dataclass(frozen=True)
class Step:
    kind: str
    operation: str = ""
    names: tuple[str, ...] = ()
    state: int = 0
    timeout: float = 3.0
    positions: tuple[float, ...] = ()


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
    return steps + arm_steps(names)


def arm_steps(names):
    steps = []
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
        "calibrate": calibrate_robot,
        "full_calibrate": calibrate_robot,
        "clear_errors": lambda names: maintenance(names),
        "sample_home": lambda names: prompted_maintenance(names, 11),
        "sample_calibrate": lambda names: prompted_maintenance(names, 4),
        "home_robot": home_robot,
    }
    for plugin in entry_points(group="catbot_supervisor.scripts"):
        if plugin.name in scripts:
            raise ValueError(f"Script already registered: {plugin.name}")
        scripts[plugin.name] = plugin.load()
    return scripts


def calibrate_robot(names):
    """Full calibration together, then ordered homing/arming with clearance."""
    groups = (
        ("flk", "frk", "blk", "brk"),
        ("flf", "frf", "blf", "brf"),
        ("bla", "bra"),
        ("fla", "fra"),
    )
    required = {name for group in groups for name in group}
    if len(names) != len(required) or set(names) != required:
        raise ValueError(
            "Robot calibration requires the complete standard 12-actuator roster"
        )
    steps = [
        Step("motor", "idle"),
        Step("wait_state", state=1),
        Step("motor", "clear_errors"),
        Step("wait_clear"),
        Step("motor", "state", tuple(names), 3),
        Step("wait_cycle", names=tuple(names), state=3, timeout=60.0),
    ]
    for group in groups:
        if group == ("fla", "fra"):
            front = ("flf", "frf")
            steps += [
                Step("position", names=front, positions=(30.0, 30.0)),
                Step(
                    "wait_position", names=front, positions=(30.0, 30.0), timeout=15.0
                ),
                Step(
                    "wait_operator",
                    "Confirm that objects are cleared before front abduction homing. "
                    "Confirming allows fla and fra to move.",
                    timeout=120.0,
                ),
            ]
        steps += [
            Step("motor", "state", group, 11),
            Step("wait_cycle", names=group, state=11, timeout=30.0),
            *arm_steps(group),
        ]
    return steps


def home_robot(names):
    """Home knees, flexion, then operator-approved abduction. Never clear faults."""
    groups = (
        ("flk", "frk", "blk", "brk"),
        ("flf", "frf", "blf", "brf"),
        ("fla", "fra", "bla", "bra"),
    )
    if set(names) != {name for group in groups for name in group}:
        raise ValueError("home_robot requires the complete standard 12-actuator roster")
    steps = [Step("motor", "idle"), Step("wait_state", state=1)]
    for index, group in enumerate(groups):
        if index == 2:
            front = ("flf", "frf")
            steps += [
                Step("position", names=front, positions=(30.0, 30.0)),
                Step(
                    "wait_position", names=front, positions=(30.0, 30.0), timeout=15.0
                ),
                Step("delay", timeout=15.0),
                Step(
                    "wait_operator",
                    "Confirm that the front legs are clear before "
                    "abduction/adduction homing. Confirming allows the motors to move.",
                    timeout=120.0,
                ),
                Step("delay", timeout=15.0),
            ]
        for name in group:
            steps += [
                Step("motor", "state", (name,), 11),
                Step("wait_state", names=(name,), state=11),
                Step("wait_state", names=(name,), state=1, timeout=30.0),
                Step("motor", "trajectory", (name,)),
                Step("motor", "hold", (name,)),
                Step("motor", "state", (name,), 8),
                Step("wait_ready", names=(name,)),
            ]
        steps.append(Step("delay", timeout=15.0))
    return steps


def prompted_maintenance(names, state):
    """Example: confirm the setup, then approve each axis before it can move.

    State 11 is controller homing; state 4 is motor calibration, not joint-zero
    measurement. Adapt prompts and axis selection to the physical procedure.
    Existing maintenance finishes by holding/arming each axis.
    """
    steps = []
    for step in maintenance(names, state):
        if step.kind == "motor" and step.operation == "state" and step.state == state:
            steps.append(
                Step(
                    "wait_operator",
                    f"Support the robot and check clearance for {step.names[0]}. "
                    f"Confirm to request controller state {state}; this can move the motor.",
                    timeout=120.0,
                )
            )
        steps.append(step)
    return steps


class ScriptRunner:
    """One step per tick; emergency replacement never waits for an old future."""

    def __init__(self, dispatch, satisfied):
        self.dispatch, self.satisfied = dispatch, satisfied
        self.steps = []
        self.index = 0
        self.deadline = None
        self.future = None
        self.error = ""
        self.prompt = None

    @property
    def active(self):
        return self.index < len(self.steps) and not self.error

    def start(self, steps):
        self.steps, self.index = list(steps), 0
        self.deadline = self.future = None
        self.error = ""
        self.prompt = None

    def respond(self, token, now):
        if not self.active or self.prompt is None or token != self.prompt["id"]:
            raise ValueError("No matching operator prompt")
        if self.deadline is None or now >= self.deadline:
            raise ValueError("Operator prompt expired")
        self.index += 1
        self.deadline = self.future = self.prompt = None

    def tick(self, now):
        if not self.active:
            return
        step = self.steps[self.index]
        try:
            if self.deadline is None:
                self.deadline = now + step.timeout
            if step.kind == "delay":
                if now >= self.deadline:
                    self.index += 1
                    self.deadline = None
                return
            if now >= self.deadline:
                raise RuntimeError(
                    f"Script step timed out: {step.kind} {step.operation}"
                )
            if step.kind == "wait_operator":
                if self.prompt is None:
                    self.prompt = {"id": uuid4().hex, "text": step.operation}
                return
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
            self.prompt = None
