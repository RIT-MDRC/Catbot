"""Read Linux counters without importing Foundation or policy on the Pi."""

import math
import os
from pathlib import Path


class PiHealth:
    def __init__(
        self, interface="eth0", foundation_pid=0, proc=Path("/proc"), sys=Path("/sys")
    ):
        if not interface or Path(interface).name != interface:
            raise ValueError("Expected a network interface name")
        self.interface, self.pid = interface, foundation_pid
        self.proc, self.sys = proc, sys
        self.previous = None
        self.process_previous = None
        self.ticks_per_second = os.sysconf("SC_CLK_TCK")

    def sample(self, now):
        result = {
            "sample_monotonic_seconds": now,
            "cpu_count": os.cpu_count(),
            "interface": self.interface,
            "interface_state": "unknown",
            "temperature_c": None,
            "system_cpu_headroom_percent": None,
            "foundation_cpu_percent_one_core": None,
            "policy_only_baseline_percent_one_core": 50.0,
            "baseline_source": "reported last-weekend policy-only measurement; approximate",
            "errors": [],
        }
        try:
            counters = [
                int(v)
                for v in (self.proc / "stat").read_text().splitlines()[0].split()[1:9]
            ]
            total, idle = sum(counters), counters[3] + counters[4]
            if self.previous is not None:
                dt, di = total - self.previous[0], idle - self.previous[1]
                if dt > 0 and di >= 0:
                    result["system_cpu_headroom_percent"] = 100.0 * di / dt
            self.previous = total, idle
        except (OSError, ValueError, IndexError) as error:
            result["errors"].append(f"cpu: {error}")
        try:
            if not self.pid:
                matches = []
                for entry in self.proc.iterdir():
                    if not entry.name.isdecimal():
                        continue
                    try:
                        args = (entry / "cmdline").read_bytes().split(b"\0")
                    except OSError:
                        continue
                    if b"foundation.main" in args or any(
                        arg.endswith(
                            (b"/foundation/main", b"/foundation/foundation/main.py")
                        )
                        for arg in args
                    ):
                        matches.append(int(entry.name))
                if len(matches) != 1:
                    raise ValueError(
                        "Set foundation_pid: expected one Foundation process"
                    )
                self.pid = matches[0]
            # comm may contain spaces/parentheses; fields after its final ')' start at stat field 3.
            fields = (
                (self.proc / str(self.pid) / "stat")
                .read_text()
                .rsplit(")", 1)[1]
                .split()
            )
            ticks, started = int(fields[11]) + int(fields[12]), int(fields[19])
            if self.process_previous is not None:
                previous_ticks, previous_now, previous_started = self.process_previous
                if (
                    started == previous_started
                    and now > previous_now
                    and ticks >= previous_ticks
                ):
                    result["foundation_cpu_percent_one_core"] = (
                        100
                        * (ticks - previous_ticks)
                        / self.ticks_per_second
                        / (now - previous_now)
                    )
            self.process_previous = ticks, now, started
            result["foundation_pid"] = self.pid
        except (OSError, ValueError, IndexError) as error:
            result["errors"].append(f"foundation: {error}")
            self.pid = 0
            self.process_previous = None
        try:
            result["interface_state"] = (
                (self.sys / "class/net" / self.interface / "operstate")
                .read_text()
                .strip()
            )
        except OSError as error:
            result["errors"].append(f"network: {error}")
        try:
            temperature = (
                float((self.sys / "class/thermal/thermal_zone0/temp").read_text())
                / 1000
            )
            if not math.isfinite(temperature):
                raise ValueError("non-finite temperature")
            result["temperature_c"] = temperature
        except (OSError, ValueError) as error:
            result["errors"].append(f"temperature: {error}")
        return result


def health_reason(sample, min_headroom=10.0, max_temperature=80.0):
    """Missing telemetry is unknown health, never a fabricated success."""
    if sample["errors"]:
        return "Pi health unavailable: " + "; ".join(sample["errors"])
    if sample["interface_state"] != "up":
        return "Pi network interface is not up"
    if sample["temperature_c"] is None or sample["temperature_c"] >= max_temperature:
        return "Pi temperature exceeds limit or is unknown"
    if (
        sample["system_cpu_headroom_percent"] is None
        or sample["system_cpu_headroom_percent"] < min_headroom
    ):
        return "Pi CPU headroom below limit or is unknown"
    if sample["foundation_cpu_percent_one_core"] is None:
        return "Foundation CPU measurement unavailable"
    return ""
