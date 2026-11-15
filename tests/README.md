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
