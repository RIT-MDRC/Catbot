"""Source/installed entry point for the isolated inference environment."""

import sys
from pathlib import Path

# The uv project is data inside the shared policy package, not a ROS installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from catbot_policy.worker import main  # noqa: E402

if __name__ == "__main__":
    main()
