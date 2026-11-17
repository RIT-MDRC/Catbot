"""Per-file floors: a well-covered file cannot hide a regression in another."""

import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())["files"]
for requirement in sys.argv[2:]:
    suffix, floor = requirement.rsplit("=", 1)
    matches = [
        data["summary"]["percent_covered"]
        for name, data in report.items()
        if name.endswith(suffix)
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one coverage entry for {suffix}: {matches}")
    actual = matches[0]
    print(f"{suffix}: {actual:.2f}% (minimum {floor}%)")
    if actual < float(floor):
        raise SystemExit(f"Coverage fell below the floor for {suffix}")
