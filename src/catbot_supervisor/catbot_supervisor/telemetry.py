"""Linux/Jetson resource facts. Missing sensors remain explicitly unavailable."""

import math
import shutil
from pathlib import Path


class Resources:
    def __init__(self, disk_path="/", proc=Path("/proc"), sys=Path("/sys")):
        self.proc, self.sys, self.disk_path = proc, sys, disk_path
        self.previous = None

    def sample(self):
        result = {
            "cpu_percent": None,
            "gpu_percent": None,
            "temperature_c": None,
            "memory_used_bytes": 0,
            "memory_total_bytes": 0,
            "disk_free_bytes": 0,
            "disk_total_bytes": 0,
            "errors": [],
        }
        try:
            counts = [
                int(v)
                for v in (self.proc / "stat").read_text().splitlines()[0].split()[1:9]
            ]
            total, idle = sum(counts), counts[3] + counts[4]
            if self.previous is not None and total > self.previous[0]:
                result["cpu_percent"] = 100 * (
                    1 - (idle - self.previous[1]) / (total - self.previous[0])
                )
            self.previous = total, idle
            memory = {
                line.split(":")[0]: int(line.split()[1]) * 1024
                for line in (self.proc / "meminfo").read_text().splitlines()
                if line.startswith(("MemTotal:", "MemAvailable:"))
            }
            result["memory_total_bytes"] = memory["MemTotal"]
            result["memory_used_bytes"] = memory["MemTotal"] - memory["MemAvailable"]
        except (OSError, ValueError, KeyError, IndexError) as error:
            result["errors"].append(f"cpu/memory: {error}")
        try:
            disk = shutil.disk_usage(self.disk_path)
            result["disk_free_bytes"], result["disk_total_bytes"] = (
                disk.free,
                disk.total,
            )
        except OSError as error:
            result["errors"].append(f"disk: {error}")
        temperatures = []
        for path in (self.sys / "class/thermal").glob("thermal_zone*/temp"):
            try:
                value = float(path.read_text()) / 1000
                if math.isfinite(value):
                    temperatures.append(value)
            except (OSError, ValueError):
                continue
        if temperatures:
            result["temperature_c"] = max(temperatures)
        else:
            result["errors"].append("temperature unavailable")
        # Jetson exposes load in tenths of a percent; desktop NVIDIA may lack it.
        candidates = [
            self.sys / "devices/gpu.0/load",
            *self.sys.glob("class/devfreq/*gpu*/device/load"),
            *self.sys.glob("class/devfreq/*ga10b*/device/load"),
        ]
        for path in candidates:
            try:
                value = float(path.read_text()) / 10
                if math.isfinite(value) and 0 <= value <= 100:
                    result["gpu_percent"] = value
                    break
            except (OSError, ValueError):
                continue
        return result
