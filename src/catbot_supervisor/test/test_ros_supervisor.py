"""Real ROS adapters and a managed policy worker; Foundation hardware is doubled."""

import json
import time
from pathlib import Path

import pytest
import rclpy
from catbot_supervisor.core import Mode
from catbot_supervisor.node import RpiSupervisor
from catbot_supervisor.orin import OrinSupervisor
from catbot_supervisor.scripts import Step
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String
from std_srvs.srv import Trigger

from catbot_interfaces.msg import (
    ActuatorErrorState,
    ActuatorKinematicState,
    ActuatorPositionCommand,
    BodyErrorState,
    BodyKinematicState,
    PolicyFeedback,
)
from catbot_interfaces.srv import (
    GetSupervisorStatus,
    MotorCommand,
    RunScript,
    SupervisorJob,
)

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures"


@pytest.mark.ros
def test_managed_orin_policy_pi_gate_scripts_and_stale_emergency(tmp_path):
    fixture = json.loads((FIXTURES / "contract.json").read_text())
    names = fixture["mapping"]["actuator_names"]
    # Fake worker validates the same bundle metadata and uses real pipes/acknowledgements.
    (tmp_path / "policy.json").write_text(json.dumps(fixture["metadata"]))
    (tmp_path / "run_worker.py").touch()
    (tmp_path / "uv.lock").touch()
    rclpy.init(
        args=[
            "--ros-args",
            "-p",
            "actuator_names:=" + json.dumps(names),
            "-p",
            f"policy_bundle:={tmp_path}",
            "-p",
            f"policy_worker_project:={tmp_path}",
            "-p",
            f"policy_uv_executable:={FIXTURES / 'fake_worker.py'}",
        ]
    )
    executor = SingleThreadedExecutor()
    pi = orin = body = None
    try:
        pi, orin = RpiSupervisor(), OrinSupervisor()
        good = {
            "errors": [],
            "interface_state": "up",
            "temperature_c": 50.0,
            "system_cpu_headroom_percent": 80.0,
            "foundation_cpu_percent_one_core": 10.0,
        }
        pi.health.sample = lambda now: dict(good)
        pi.health_sample = dict(good)
        resources = {
            "cpu_percent": 10.0,
            "gpu_percent": None,
            "temperature_c": 50.0,
            "memory_used_bytes": 1000,
            "memory_total_bytes": 2000,
            "disk_free_bytes": 8 * 1024**3,
            "disk_total_bytes": 16 * 1024**3,
            "errors": [],
        }
        orin.resources.sample = lambda: dict(resources)
        orin.resource_sample = dict(resources)
        body = Node("supervisor_test_body", use_global_arguments=False)
        states = dict.fromkeys(names, 1)
        positions = dict.fromkeys(names, 0.0)
        faults = dict.fromkeys(names, 0)
        operations, received, completing = [], [], {}
        state_pub = body.create_publisher(
            BodyErrorState,
            "/body/state/error",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        feedback_pub = body.create_publisher(PolicyFeedback, "/policy/feedback", 1)
        position_pub = body.create_publisher(
            BodyKinematicState, "/body/state/position", 1
        )
        sensors_enabled = [True]
        contract_pub = body.create_publisher(
            String,
            "/policy/contract",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )

        def motor(request, response):
            assert request.operation not in ("trajectory", "hold"), (
                "Arming must preserve controller configuration and target"
            )
            operations.append(
                (request.operation, request.state, list(request.actuator_names))
            )
            for name in request.actuator_names or names:
                if request.operation in ("idle", "emergency"):
                    states[name] = 1
                    completing.pop(name, None)
                elif request.operation == "state":
                    states[name] = request.state
                    if request.state in (4, 11):
                        completing[name] = time.monotonic() + 0.15
            response.success, response.message = True, "sent"
            return response

        body.create_service(MotorCommand, "/body/control/motor", motor)

        def position_command(message):
            received.append(message)
            positions.update(zip(message.actuator_names, message.positions_degrees))

        body.create_subscription(
            ActuatorPositionCommand, "/body/control/position", position_command, 1
        )
        body.create_subscription(
            ActuatorPositionCommand, "/body/control/move/position", position_command, 1
        )

        def publish():
            now = time.monotonic()
            for name, deadline in list(completing.items()):
                if now >= deadline:
                    states[name] = 1
                    del completing[name]
            state_pub.publish(
                BodyErrorState(
                    stamp=body.get_clock().now().to_msg(),
                    actuators=[
                        ActuatorErrorState(
                            actuator_name=name,
                            axis_id=index,
                            heartbeat_available=True,
                            ready=states[name] == 8,
                            axis_state=states[name],
                            encoder_error_flags=faults[name],
                        )
                        for index, name in enumerate(names)
                    ],
                )
            )
            position_pub.publish(
                BodyKinematicState(
                    actuators=[
                        ActuatorKinematicState(
                            actuator_name=name,
                            valid=True,
                            position_degrees=positions[name],
                        )
                        for name in names
                    ]
                )
            )
            contract_pub.publish(
                String(
                    data=json.dumps(
                        {
                            "version": 1,
                            **fixture["metadata"],
                            "mapping": fixture["mapping"],
                        }
                    )
                )
            )
            if sensors_enabled[0]:
                values = dict(fixture["feedback"])
                for key in ("previous_contact", "has_stance"):
                    values[key] = [bool(v) for v in values[key]]
                feedback_pub.publish(PolicyFeedback(**values))

        body.create_timer(0.02, publish)
        for node in (pi, orin, body):
            executor.add_node(node)

        def until(predicate, timeout=15):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                executor.spin_once(timeout_sec=0.01)
            assert predicate(), pi.gate.reason + " " + pi.runner.error

        def call(service_type, topic, request):
            client = body.create_client(service_type, topic)
            until(client.service_is_ready)
            future = client.call_async(request)
            until(future.done)
            result = future.result()
            assert result.success, result.message
            body.destroy_client(client)
            return result

        until(lambda: pi.gate.mode == Mode.IDLE)
        until(lambda: not orin.preflight_reason() and not pi.gate.orin_degraded)
        assert not received and not orin.jobs.running("policy")
        assert not pi.runner.active and not pi.script_name
        call(RunScript, "/rpi/supervisor/script", RunScript.Request(name="startup"))
        until(lambda: pi.gate.mode == Mode.READY, timeout=30)
        assert not received, "Policy proposals must not cross the gate before RUNNING"
        assert orin.jobs.running("policy")
        assert [
            names_
            for operation, state, names_ in operations
            if operation == "state" and state == 4
        ] == [[name] for name in names]
        status = json.loads(
            call(
                GetSupervisorStatus,
                "/orin/supervisor/get_status",
                GetSupervisorStatus.Request(name="policy"),
            ).status_json
        )
        assert status["version"] == 1 and status["policy"]["ready"]
        assert (
            status["policy"]["verified"]
            and status["policy"]["bundle_id"] == fixture["metadata"]["policy_sha256"]
        )
        assert pi.orin_preflight_passed and pi.orin_policy_verified
        # A subcomponent fault rejects homing without issuing any motor commands.
        faults["flk"] = 4
        until(lambda: pi.body["flk"].encoder_error_flags == 4)
        before = len(operations)
        result = pi.run_script(
            RunScript.Request(name="home_robot"), RunScript.Response()
        )
        assert not result.success and "encoder_error_flags" in result.message
        assert len(operations) == before
        faults["flk"] = 0
        until(lambda: pi.body["flk"].encoder_error_flags == 0)
        call(RunScript, "/rpi/supervisor/script", RunScript.Request(name="home_robot"))
        until(lambda: pi.runner.prompt is not None, timeout=60)
        assert positions["flf"] == positions["frf"] == 30.0
        assert [
            ns for op, state, ns in operations if op == "state" and state == 11
        ] == [[n] for n in ("flk", "frk", "blk", "brk", "flf", "frf", "blf", "brf")]
        # No abduction operation may precede the operator's current confirmation.
        token = pi.runner.prompt["id"]
        call(RunScript, "/rpi/supervisor/respond", RunScript.Request(name=token))
        until(lambda: pi.gate.mode == Mode.HOLDING, timeout=60)
        assert [
            ns for op, state, ns in operations if op == "state" and state == 11
        ] == [
            [n]
            for n in (
                "flk",
                "frk",
                "blk",
                "brk",
                "flf",
                "frf",
                "blf",
                "brf",
                "fla",
                "fra",
                "bla",
                "bra",
            )
        ]
        received.clear()
        call(Trigger, "/rpi/supervisor/policy_stop", Trigger.Request())
        until(lambda: not orin.jobs.children and not pi.gate.orin_degraded)
        assert pi.gate.mode == Mode.HOLDING and all(s == 8 for s in states.values())
        call(
            SupervisorJob,
            "/orin/supervisor/job",
            SupervisorJob.Request(name="policy", operation="start"),
        )
        until(
            lambda: (
                orin.policy_ready
                and pi.gate.action_at is not None
                and time.monotonic() - pi.gate.action_at < pi.gate.limits.action_age
            ),
            timeout=25,
        )
        assert not received and all(s == 8 for s in states.values())
        call(Trigger, "/rpi/supervisor/run", Trigger.Request())
        until(lambda: len(received) >= 5)
        assert list(received[-1].actuator_names) == names
        sensors_enabled[0] = False
        until(lambda: pi.gate.mode == Mode.EMERGENCY)
        count = len(received)
        until(
            lambda: (
                not pi.runner.active and all(value == 1 for value in states.values())
            )
        )
        until(lambda: not orin.jobs.running("policy"))
        assert len(received) == count, "Emergency forwarded an action"
        sensors_enabled[0] = True
        call(Trigger, "/rpi/supervisor/recover", Trigger.Request())
        until(lambda: pi.gate.mode == Mode.IDLE)
        assert len(received) == count
        old_session = orin.session
        call(
            RunScript,
            "/rpi/supervisor/script",
            RunScript.Request(name="restart_policy"),
        )
        until(
            lambda: (
                orin.session != old_session
                and orin.policy_ready
                and pi.gate.mode == Mode.READY
            ),
            timeout=25,
        )
        assert len(orin.jobs.children) == 1
        assert len(received) == count
        call(RunScript, "/rpi/supervisor/script", RunScript.Request(name="shutdown"))
        until(lambda: not pi.runner.active)
        assert pi.gate.mode == Mode.SHUTDOWN
        # Independent clock replies do not renew the Pi action/probe lease.
        call(
            SupervisorJob,
            "/orin/supervisor/job",
            SupervisorJob.Request(name="policy", start=True),
        )
        until(lambda: orin.jobs.running("policy"))
        pi.probe_timer.cancel()
        until(lambda: not orin.jobs.running("policy"))
        assert not orin.jobs.pending
    finally:
        executor.shutdown()
        for node in (pi, orin, body):
            if node is not None:
                node.destroy_node()
        rclpy.shutdown()


@pytest.mark.ros
def test_local_homing_without_orin_or_policy():
    names = json.loads((FIXTURES / "contract.json").read_text())["mapping"][
        "actuator_names"
    ]
    rclpy.init(args=["--ros-args", "-p", "actuator_names:=" + json.dumps(names)])
    executor = SingleThreadedExecutor()
    pi = body = None
    try:
        pi = RpiSupervisor()
        pi.health_sample = {
            "errors": [],
            "interface_state": "up",
            "temperature_c": 50.0,
            "system_cpu_headroom_percent": 80.0,
            "foundation_cpu_percent_one_core": 10.0,
        }
        pi.health.sample = lambda now: dict(pi.health_sample)
        body = Node("local_homing_test_body", use_global_arguments=False)
        states, positions, faults = (
            dict.fromkeys(names, 1),
            dict.fromkeys(names, 0.0),
            dict.fromkeys(names, 0),
        )
        operations, completing = [], {}
        calibrating = set()
        state_pub = body.create_publisher(
            BodyErrorState,
            "/body/state/error",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        position_pub = body.create_publisher(
            BodyKinematicState, "/body/state/position", 1
        )

        def motor(request, response):
            assert request.operation not in ("trajectory", "hold"), (
                "Arming must preserve controller configuration and target"
            )
            operations.append(
                (request.operation, request.state, list(request.actuator_names))
            )
            if request.operation == "state" and request.state == 8:
                assert all(state != 11 for state in states.values()), (
                    "Arming before the complete homing group finished"
                )
            for index, name in enumerate(request.actuator_names or names):
                if request.operation in ("idle", "emergency"):
                    states[name] = 1
                    completing.pop(name, None)
                elif request.operation == "state":
                    states[name] = 4 if request.state == 3 else request.state
                    if request.state == 3:
                        calibrating.add(name)
                    if request.state in (3, 4, 11):
                        completing[name] = time.monotonic() + 0.1 + index * 0.04
            response.success = True
            return response

        body.create_service(MotorCommand, "/body/control/motor", motor)

        def explicit_move(msg):
            if list(msg.positions_degrees) == [0.0, 0.0]:
                assert all(states[name] == 8 for name in ("fla", "fra")), (
                    "Front flexion returned before front abduction was homed and armed"
                )
            positions.update(zip(msg.actuator_names, msg.positions_degrees))
            for name in msg.actuator_names:
                states[name] = 8

        body.create_subscription(
            ActuatorPositionCommand,
            "/body/control/move/position",
            explicit_move,
            1,
        )

        def publish():
            for name, deadline in list(completing.items()):
                if time.monotonic() >= deadline:
                    if name in calibrating and states[name] == 4:
                        states[name] = 7
                        completing[name] = time.monotonic() + 0.08
                        continue
                    states[name] = 1
                    calibrating.discard(name)
                    del completing[name]
            state_pub.publish(
                BodyErrorState(
                    actuators=[
                        ActuatorErrorState(
                            actuator_name=name,
                            heartbeat_available=True,
                            ready=states[name] == 8,
                            axis_state=states[name],
                            controller_error_flags=faults[name],
                        )
                        for name in names
                    ]
                )
            )
            position_pub.publish(
                BodyKinematicState(
                    actuators=[
                        ActuatorKinematicState(
                            actuator_name=name,
                            valid=True,
                            position_degrees=positions[name],
                        )
                        for name in names
                    ]
                )
            )

        body.create_timer(0.02, publish)
        executor.add_node(pi)
        executor.add_node(body)

        def until(predicate, timeout=10):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                executor.spin_once(timeout_sec=0.01)
            assert predicate(), pi.gate.reason

        def script():
            result = pi.run_script(
                RunScript.Request(name="home_robot"), RunScript.Response()
            )
            assert result.success, result.message

        until(lambda: pi.gate.mode == Mode.IDLE and pi.body_fresh())
        # An explicit script move can start from idle without separate arm steps.
        pi.scripts["move_check"] = lambda names: [
            Step("position", names=("flf",), positions=(12.0,)),
            Step("wait_position", names=("flf",), positions=(12.0,)),
            Step("wait_operator", "Move complete; keep the remaining axes idle"),
        ]
        assert pi.run_script(
            RunScript.Request(name="move_check"), RunScript.Response()
        ).success
        until(lambda: pi.runner.prompt is not None)
        assert positions["flf"] == 12.0 and states["flf"] == 8
        assert all(states[name] == 1 for name in names if name != "flf")
        assert not any(op == "state" and state == 8 for op, state, ns in operations)
        pi.emergency(Trigger.Request(), Trigger.Response())
        until(lambda: not pi.runner.active and all(s == 1 for s in states.values()))
        # A new emergency supersedes a pending Foundation recovery response.
        assert pi.recover(Trigger.Request(), Trigger.Response()).success
        pi.emergency(Trigger.Request(), Trigger.Response())
        until(lambda: not pi.runner.active)
        assert pi.gate.mode == Mode.EMERGENCY
        assert pi.recover(Trigger.Request(), Trigger.Response()).success
        until(lambda: pi.gate.mode == Mode.IDLE)
        statuses = []
        body.create_subscription(
            String,
            "/rpi/supervisor/status",
            lambda msg: statuses.append(json.loads(msg.data)),
            1,
        )
        pi.scripts["future_check"] = lambda names: [
            Step("wait_operator", "Future script prompt")
        ]
        until(lambda: statuses and "future_check" in statuses[-1]["available_scripts"])
        assert not pi.runner.active
        result = pi.run_script(
            RunScript.Request(name="future_check"), RunScript.Response()
        )
        assert result.success
        until(lambda: pi.runner.prompt is not None)
        assert pi.runner.prompt["text"] == "Future script prompt"
        pi.emergency(Trigger.Request(), Trigger.Response())
        until(lambda: not pi.runner.active)
        assert pi.recover(Trigger.Request(), Trigger.Response()).success
        until(lambda: pi.gate.mode == Mode.IDLE)
        # Calibration is independently requested and does not need a policy peer.
        result = pi.run_script(
            RunScript.Request(name="calibrate"), RunScript.Response()
        )
        assert result.success
        until(lambda: pi.runner.prompt is not None)
        assert [ns for op, state, ns in operations if op == "state" and state == 3] == [
            names
        ]
        assert [
            ns for op, state, ns in operations if op == "state" and state == 11
        ] == [
            ["flk", "frk", "blk", "brk"],
            ["flf", "frf", "blf", "brf"],
            ["bla", "bra"],
        ]
        assert positions["flf"] == positions["frf"] == 30.0
        assert states["fla"] == states["fra"] == 1
        assert all(states[name] == 8 for name in names if name not in ("fla", "fra"))
        for _ in range(10):
            executor.spin_once(timeout_sec=0.01)
        assert states["fla"] == states["fra"] == 1  # Confirmation remains necessary.
        assert pi.respond(
            RunScript.Request(name=pi.runner.prompt["id"]), RunScript.Response()
        ).success
        until(lambda: pi.gate.mode == Mode.HOLDING)
        assert [ns for op, state, ns in operations if op == "state" and state == 11][
            -1
        ] == ["fla", "fra"]
        assert all(state == 8 for state in states.values())
        assert positions["flf"] == positions["frf"] == 0.0
        assert not pi.jobs.service_is_ready()
        # A fault still aborts a local sequence during its buffer, without Orin.
        script()
        until(
            lambda: (
                pi.runner.active and pi.runner.steps[pi.runner.index].kind == "delay"
            )
        )
        faults["flk"] = 4
        until(lambda: pi.gate.mode == Mode.EMERGENCY)
        until(lambda: not pi.runner.active and all(s == 1 for s in states.values()))
        faults["flk"] = 0
        until(lambda: pi.body["flk"].controller_error_flags == 0)
        assert pi.recover(Trigger.Request(), Trigger.Response()).success
        until(lambda: pi.gate.mode == Mode.IDLE)
        operations.clear()
        script()
        until(lambda: pi.runner.prompt is not None, timeout=60)
        assert positions["flf"] == positions["frf"] == 30.0
        assert not any(
            op == "state" and state == 11 and ns == ["fla"]
            for op, state, ns in operations
        )
        assert pi.respond(
            RunScript.Request(name=pi.runner.prompt["id"]), RunScript.Response()
        ).success
        until(lambda: pi.gate.mode == Mode.HOLDING, timeout=60)
        assert all(s == 8 for s in states.values())
        assert pi.gate.heartbeat_at is None
        assert not pi.run(Trigger.Request(), Trigger.Response()).success
        assert not pi.jobs.service_is_ready()
        # All subcomponent faults continue to trigger disarm while locally holding.
        faults["fra"] = 8
        until(lambda: pi.gate.mode == Mode.EMERGENCY)
        until(lambda: not pi.runner.active and all(s == 1 for s in states.values()))
    finally:
        executor.shutdown()
        for node in (pi, body):
            if node is not None:
                node.destroy_node()
        rclpy.shutdown()


@pytest.mark.ros
@pytest.mark.parametrize("signal_name", ["SIGINT", "SIGTERM"])
def test_pi_process_keeps_ros_live_for_signal_cleanup(tmp_path, signal_name):
    import signal
    import subprocess
    import sys

    ready = tmp_path / "ready"
    events = tmp_path / "events"
    code = r"""
import sys
from pathlib import Path
from types import SimpleNamespace
import rclpy
from rclpy.node import Node
import catbot_supervisor.node as target
ready, events = map(Path, sys.argv[1:])
def record(value):
    with events.open('a') as stream:
        stream.write(value + '\n')
class Fake(Node):
    def __init__(self):
        super().__init__('shutdown_test_pi')
        self.runner = SimpleNamespace(active=True)
        self.create_timer(.02, self.tick)
    def tick(self):
        ready.touch()
        if events.exists():
            self.runner.active = False
    def enter_emergency(self, reason):
        assert rclpy.ok(), 'ROS shut down before emergency cleanup'
        record('emergency')
    def destroy_node(self):
        assert rclpy.ok(), 'ROS shut down before node destruction'
        record('destroy')
        return super().destroy_node()
target.RpiSupervisor = Fake
target.main()
assert not rclpy.ok()
record('context_shutdown')
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(ready), str(events)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while (
            not ready.exists() and child.poll() is None and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert ready.exists(), "Child did not start spinning"
        child.send_signal(getattr(signal, signal_name))
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0, stdout + stderr
        assert events.read_text().splitlines() == [
            "emergency",
            "destroy",
            "context_shutdown",
        ]
        assert "Traceback" not in stderr
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
