"""Pure bookkeeping for supervised manual targets; no hardware I/O."""

import math
from dataclasses import dataclass


@dataclass
class ManualTarget:
    position: float
    accepted_at: float
    last_update: float
    streaming: bool


class ManualControl:
    """Track accepted targets and session-local ordering using monotonic time."""

    def __init__(self, drag_timeout=0.5, move_timeout=15.0):
        if not all(math.isfinite(x) and x > 0 for x in (drag_timeout, move_timeout)):
            raise ValueError("manual timeouts must be finite and positive")
        self.drag_timeout = drag_timeout
        self.move_timeout = move_timeout
        self.targets = {}
        self.sequences = {}

    def accept(
        self, *, client, sequence, axis, position, minimum, maximum, now, streaming
    ):
        if not client or len(client) > 128 or not axis:
            raise ValueError("manual client and axis are required")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError("invalid manual command sequence")
        if not all(math.isfinite(x) for x in (position, minimum, maximum, now)):
            raise ValueError("manual values must be finite")
        if minimum >= maximum or not minimum <= position <= maximum:
            raise ValueError("manual target outside configured limits")
        key = (client, axis)
        if sequence <= self.sequences.get(key, 0):
            raise ValueError("manual command out of order")
        self.sequences[key] = sequence
        self.targets[axis] = ManualTarget(position, now, now, streaming)

    def tick(self, now, feedback):
        """Retire timed-out or settled non-streaming targets; return timed-out axes."""
        timed_out = []
        for axis, target in list(self.targets.items()):
            dragging = (
                target.streaming and 0 <= now - target.last_update <= self.drag_timeout
            )
            if now - target.accepted_at >= self.move_timeout:
                timed_out.append(axis)
                del self.targets[axis]
                continue
            sample = feedback.get(axis)
            if not dragging and sample is not None:
                valid, position, velocity = sample
                if (
                    valid
                    and math.isfinite(position)
                    and math.isfinite(velocity)
                    and abs(position - target.position) <= 1.0
                    and abs(velocity) <= 1.0
                ):
                    del self.targets[axis]
        return timed_out

    def active(self):
        return bool(self.targets)
