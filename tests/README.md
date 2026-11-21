# Automated checks

Both repositories run `Policy CI` on every push and pull request. The unit job
runs the existing foundation/UI behavioral tests and the full policy suite,
including export parity. Python 3.14 policy test dependencies are pinned in
`tests/uv.lock`; foundation/UI use the root Python 3.10 lock.

```sh
uv run --locked --project tests python -m pytest -m 'not ros' \
  --cov=catbot_policy.runtime --cov=catbot_policy.deployment \
  --cov-report=json:policy-coverage.json
uv run --locked --project tests python tests/check_coverage.py policy-coverage.json \
  catbot_policy/runtime.py=92 catbot_policy/deployment.py=90
```

The separate ROS job builds generated interfaces in ROS Humble, then runs
`pytest -m ros src/catbot_policy/test/test_ros_smoke.py`. ROS modules are excluded
from default collection; explicitly selecting them requires working ROS imports
and cannot silently skip. Disable pytest plugin autoload for these tests to avoid
Humble's unrelated launch_testing collection hook. The adapters use real ROS and
stdlib fake workers; these checks do not validate CUDA or physical hardware.

`fixtures/contract.json` is a versioned golden contract, not generated during tests.
It pins all 90 observation entries and forward/clamped/inverse mapping vectors.
Orin reads this exact file via its pinned Catbot submodule. Change it deliberately
with a contract change, and review both consumers. `fake_worker.py` provides
normal protocol replies plus malformed, oversized, wrong-version, timeout and
SIGTERM-ignoring modes. Process tests use real pipes and verify worker cleanup.

Coverage floors apply separately to each file; CI uploads coverage JSON and JUnit
reports even on failure. Orin additionally enforces 51% for scenarios.py's pure
paths; its ROS launch assembly is exercised in the separate integration job.

Behavior tests supply their own mappings and motion profiles. Do not assert the
current calibration or deployment defaults: changing those values should not
require rewriting unit tests. Test parsing, conversion, bounds, and failure
behavior using explicit inputs. Keep the versioned golden fixture for shared
observation/action compatibility and the ROS tests for real message serialization.


Supervisor checks run in the root Python 3.10 suite:

```sh
uv run --locked --group dev python -m pytest src/catbot_supervisor/test
```

CI also builds `catbot_supervisor` and runs
`src/catbot_supervisor/test/test_ros_supervisor.py` in its ROS job. This test uses
real Pi/Orin ROS adapters and an actual managed policy-adapter process with the
stdlib fake inference worker. It checks sequential startup, a closed gate before
running, forwarding acknowledgements, stale-stream emergency disarm, explicit
recovery, and shutdown. Foundation hardware and Pi health readings are doubled;
this does not establish physical motor behavior or measured Pi CPU headroom.

The local calibration ROS test requests full calibration as one batch, simulates
different per-axis completion times and calibration substates, and checks that
no arming request occurs while any actuator remains in homing. It checks the
ordered homing groups, settled +30-degree front-flexion move, required operator
confirmation before front-abduction homing, and final holding without policy.
