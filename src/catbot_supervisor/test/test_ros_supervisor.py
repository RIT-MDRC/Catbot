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
    SupervisorStatus,
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
                if (
                    request.operation in ("idle", "emergency")
                    or request.operation == "fault_stop"
                    and (states[name] != 8 or faults[name])
                ):
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
        until(lambda: pi.gate.mode == Mode.EMERGENCY and not pi.runner.active)
        faults["flk"] = 0
        until(lambda: pi.body["flk"].encoder_error_flags == 0)
        assert pi.gate.mode == Mode.EMERGENCY
        call(Trigger, "/rpi/supervisor/recover", Trigger.Request())
        until(lambda: pi.gate.mode == Mode.IDLE)
        call(RunScript, "/rpi/supervisor/script", RunScript.Request(name="home_robot"))
        until(lambda: pi.runner.prompt is not None, timeout=60)
        assert positions["flf"] == positions["frf"] == 30.0
        assert [
            ns for op, state, ns in operations if op == "state" and state == 11
        ] == [["flk", "frk", "blk", "brk", "flf", "frf", "blf", "brf"]]
        # No abduction operation may precede the operator's current confirmation.
        token = pi.runner.prompt["id"]
        call(RunScript, "/rpi/supervisor/respond", RunScript.Request(name=token))
        until(lambda: pi.gate.mode == Mode.HOLDING, timeout=60)
        assert [
            ns for op, state, ns in operations if op == "state" and state == 11
        ] == [
            ["flk", "frk", "blk", "brk", "flf", "frf", "blf", "brf"],
            ["fla"],
            ["fra"],
            ["bla"],
            ["bra"],
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
        faults["bra"] = 256
        until(lambda: pi.gate.mode == Mode.EMERGENCY and not pi.runner.active)
        count = len(received)
        assert pi.hold_healthy and states["bra"] == 1
        assert all(states[n] == 8 for n in names if n != "bra")
        until(lambda: not orin.jobs.running("policy"))
        assert len(received) == count, "Actuator fault forwarded an action"
        faults["bra"] = 0
        until(lambda: pi.body["bra"].encoder_error_flags == 0)
        assert pi.gate.mode == Mode.EMERGENCY
        call(Trigger, "/rpi/supervisor/recover", Trigger.Request())
        until(lambda: pi.gate.mode == Mode.IDLE)
        assert len(received) == count
        call(
            RunScript,
            "/rpi/supervisor/script",
            RunScript.Request(name="restart_policy"),
        )
        until(lambda: pi.gate.mode == Mode.READY, timeout=25)
        call(Trigger, "/rpi/supervisor/run", Trigger.Request())
        until(lambda: len(received) >= count + 5)
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
            dict.fromkeys(names, 7.0),
            dict.fromkeys(names, 0),
        )
        axis_faults = dict.fromkeys(names, 0)
        operations, completing = [], {}
        calibrating = set()
        zero_moves = []
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
                assert not calibrating, "Arming before every axis finished calibration"
                assert all(state != 11 for state in states.values()), (
                    "Arming before the complete homing group finished"
                )
            if (
                request.operation == "state"
                and request.state == 11
                and any(op == "state" and state == 3 for op, state, _ in operations)
                and not any(
                    op == "state" and state == 11 for op, state, _ in operations[:-1]
                )
            ):
                assert all(
                    states[name] == 8 for name in ("fla", "fra", "bla", "bra")
                ), "Abduction axes must be armed after calibration and before homing"
            for index, name in enumerate(request.actuator_names or names):
                if request.operation in ("idle", "emergency"):
                    states[name] = 1
                    completing.pop(name, None)
                elif request.operation == "clear_errors":
                    axis_faults[name] = 0
                elif request.operation == "state":
                    states[name] = 4 if request.state == 3 else request.state
                    if request.state == 3:
                        calibrating.add(name)
                    if request.state in (3, 4, 11):
                        completing[name] = time.monotonic() + 0.1 + index * 0.04
                elif request.operation == "fault_stop" and (
                    states[name] != 8 or faults[name] or axis_faults[name]
                ):
                    states[name] = 1
                    completing.pop(name, None)
            response.success = True
            return response

        body.create_service(MotorCommand, "/body/control/motor", motor)

        def explicit_move(msg):
            targets = dict(zip(msg.actuator_names, msg.positions_degrees))
            if targets == dict.fromkeys(names, 0.0):
                assert all(state == 8 for state in states.values())
                assert [
                    ns for op, state, ns in operations if op == "state" and state == 11
                ][-1] == ["fla", "fra"]
                zero_moves.append(dict(targets))
                # One joint has not reached its target: holding must wait for it.
                targets.pop(names[-1])
            positions.update(targets)
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
                            axis_error_flags=axis_faults[name],
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
        reason = pi.local_reason()
        assert reason.startswith("Foundation actuator not ready: ")
        assert "brk (axis_state=1, heartbeat_available=True" in reason
        assert "motor_error_flags=0 [NONE]" in reason
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
            SupervisorStatus,
            "/rpi/supervisor/status",
            lambda msg: statuses.append(
                {
                    "available_scripts": list(msg.available_scripts),
                    "operator_prompt": {
                        "id": msg.operator_prompt.id,
                        "text": msg.operator_prompt.text,
                    },
                }
            ),
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
            ["flk", "frk", "blk", "brk", "flf", "frf", "blf", "brf"],
            ["bla", "bra"],
        ]
        assert positions["flf"] == positions["frf"] == 30.0
        assert all(state == 8 for state in states.values())
        assert positions["flk"] == positions["brk"] == 7.0
        for _ in range(10):
            executor.spin_once(timeout_sec=0.01)
        assert not any(
            op == "state" and state == 11 and ns == ["fla", "fra"]
            for op, state, ns in operations
        )  # Confirmation remains necessary even though these axes are holding.
        assert pi.respond(
            RunScript.Request(name=pi.runner.prompt["id"]), RunScript.Response()
        ).success
        until(lambda: bool(zero_moves))
        assert zero_moves == [dict.fromkeys(names, 0.0)]
        for _ in range(20):
            executor.spin_once(timeout_sec=0.01)
        assert pi.runner.active and pi.gate.mode != Mode.HOLDING
        positions[names[-1]] = 0.0
        until(lambda: pi.gate.mode == Mode.HOLDING)
        assert [ns for op, state, ns in operations if op == "state" and state == 11][
            -1
        ] == ["fla", "fra"]
        assert all(state == 8 for state in states.values())
        assert all(position == 0.0 for position in positions.values())
        assert not pi.jobs.service_is_ready()
        # A single actuator fault holds every other healthy axis, with no peer.
        faults["bra"] = 256
        until(lambda: pi.gate.mode == Mode.EMERGENCY and not pi.runner.active)
        assert pi.hold_healthy
        assert states["bra"] == 1
        assert all(states[n] == 8 for n in names if n != "bra")
        assert "bra" in pi.gate.reason
        assert "controller_error_flags=256 [UNDECODED]" in pi.gate.reason
        assert "motor_error_flags=0 [NONE]" in pi.gate.reason
        assert pi.recover(Trigger.Request(), Trigger.Response()).success
        faults["bra"] = 0
        until(lambda: pi.gate.mode == Mode.IDLE)
        assert all(states[n] == 8 for n in names if n != "bra")
        # Explicit e-stop still disarms every motor.
        pi.emergency(Trigger.Request(), Trigger.Response())
        until(lambda: not pi.runner.active and all(s == 1 for s in states.values()))
        assert not pi.hold_healthy
        axis_faults["bra"] = 8192
        until(lambda: pi.body["bra"].axis_error_flags == 8192)
        recovery_start = len(operations)
        assert pi.recover(Trigger.Request(), Trigger.Response()).success
        until(lambda: pi.gate.mode == Mode.IDLE)
        assert operations[recovery_start:] == [
            ("clear_errors", 0, names), ("recover", 0, [])
        ]
        assert all(state == 1 for state in states.values())
        # A fault also aborts a local sequence, retaining healthy knees/flexion.
        script()
        until(
            lambda: (
                pi.runner.active and pi.runner.steps[pi.runner.index].kind == "delay"
            )
        )
        faults["flk"] = 4
        until(lambda: pi.gate.mode == Mode.EMERGENCY)
        until(lambda: not pi.runner.active)
        assert states["flk"] == 1
        assert all(
            states[n] == 8 for n in ("frk", "blk", "brk", "flf", "frf", "blf", "brf")
        )
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
        # A later local fault retains holds; explicit e-stop overrides it.
        faults["fra"] = 8
        until(lambda: pi.gate.mode == Mode.EMERGENCY)
        until(lambda: not pi.runner.active)
        assert pi.hold_healthy and states["fra"] == 1
        assert all(states[n] == 8 for n in names if n != "fra")
        pi.emergency(Trigger.Request(), Trigger.Response())
        until(lambda: not pi.runner.active and all(s == 1 for s in states.values()))
        assert not pi.hold_healthy
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


@pytest.mark.ros
def test_zero_dispatch_publishes_only_to_non_arming_position_path(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    import catbot_supervisor.node as supervisor_node

    monkeypatch.setattr(supervisor_node, "health_reason", lambda *_: "")
    axis = SimpleNamespace(
        heartbeat_available=True, axis_error_flags=0, axis_state=8, ready=True
    )
    output = Mock()
    output.get_subscription_count.return_value = 1
    moves = Mock()
    moves.get_subscription_count.return_value = 1
    pi = SimpleNamespace(
        script_name="zero_flk",
        state_cycle=None,
        script_link_required=False,
        health_sample={},
        min_headroom=0,
        max_temperature=80,
        body_fresh=lambda: True,
        body={"flk": axis},
        output=output,
        moves=moves,
    )
    step = Step("position_armed", names=("flk",), positions=(0.0,))
    result = RpiSupervisor.dispatch(pi, step)
    assert result.result().success
    msg = output.publish.call_args.args[0]
    assert list(msg.actuator_names) == ["flk"]
    assert list(msg.positions_degrees) == [0.0]
    moves.publish.assert_not_called()
    axis.axis_state = 1
    with pytest.raises(RuntimeError, match="closed loop"):
        RpiSupervisor.dispatch(pi, step)
    assert output.publish.call_count == 1


@pytest.mark.ros
def test_cpu_health_warning_is_advisory_and_rate_limited(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    import catbot_supervisor.node as supervisor_node

    clock = [100.0]
    monkeypatch.setattr(supervisor_node.time, "monotonic", lambda: clock[0])
    sample = {
        "errors": [],
        "interface_state": "up",
        "temperature_c": 50.0,
        "system_cpu_headroom_percent": 3.0,
        "foundation_cpu_percent_one_core": 95.0,
    }
    logger = Mock()
    node = SimpleNamespace(
        health=SimpleNamespace(sample=lambda _: dict(sample)),
        min_headroom=10.0,
        get_logger=lambda: logger,
    )
    RpiSupervisor.sample_health(node)
    assert "headroom low" in logger.warning.call_args.args[0]
    assert supervisor_node.health_reason(node.health_sample) == ""
    clock[0] = 101.0
    RpiSupervisor.sample_health(node)
    assert logger.warning.call_count == 1
    clock[0] = 131.0
    RpiSupervisor.sample_health(node)
    assert logger.warning.call_count == 2


@pytest.mark.ros
@pytest.mark.parametrize('outcome', ['clear', 'persistent', 'send_failure', 'superseded'])
@pytest.mark.parametrize('fault', [0, 8192, 768])
@pytest.mark.parametrize('hold_healthy', [False, True])
def test_recover_clears_all_errors_and_preserves_original_stop_checks(outcome, fault, hold_healthy):
    from concurrent.futures import Future
    from types import MethodType, SimpleNamespace
    from unittest.mock import Mock
    from catbot_supervisor.homing import ERROR_FIELDS

    axis = SimpleNamespace(**dict.fromkeys(ERROR_FIELDS, 0), axis_state=1, heartbeat_available=True)
    axis.axis_error_flags = fault
    if fault == 768:
        axis.encoder_error_flags = 128
        axis.controller_error_flags = 32
    calls, futures = [], []
    def send(request):
        calls.append(request)
        future = Future()
        futures.append(future)
        return future
    pi = SimpleNamespace(
        body={'a': axis}, names=('a',), body_at=0.0,
        body_fresh=lambda: True, emergency_stopped=lambda: True,
        gate=SimpleNamespace(mode=Mode.EMERGENCY, recover=Mock()),
        runner=SimpleNamespace(active=False), reboot_wait=None,
        recovery_deadline=None, recovery_generation=0, recovery_clear_at=None,
        hold_healthy=hold_healthy, enter_emergency=Mock(),
        motor=SimpleNamespace(service_is_ready=lambda: True, call_async=send),
    )
    pi._recover_foundation = MethodType(RpiSupervisor._recover_foundation, pi)
    pi._advance_recovery = MethodType(RpiSupervisor._advance_recovery, pi)
    assert RpiSupervisor.recover(pi, Trigger.Request(), Trigger.Response()).success
    assert [(r.operation, list(r.actuator_names)) for r in calls] == [('clear_errors', ['a'])]
    assert not RpiSupervisor.recover(pi, Trigger.Request(), Trigger.Response()).success
    if outcome == 'superseded':
        pi.recovery_generation += 1
    futures[0].set_result(SimpleNamespace(success=outcome != 'send_failure', message='send failed'))
    if outcome == 'send_failure':
        pi.enter_emergency.assert_called_once()
    elif outcome == 'superseded':
        assert pi.recovery_clear_at is None
    else:
        if outcome == 'clear':
            for field in ERROR_FIELDS:
                setattr(axis, field, 0)
        else:
            axis.axis_error_flags = 8192
        pi.body_at = pi.recovery_clear_at - 0.1
        pi._advance_recovery()
        assert len(calls) == 1  # An older report cannot complete recovery.
        pi.body_at = pi.recovery_clear_at + 0.1
        pi._advance_recovery()
        if outcome == 'persistent' and hold_healthy:
            assert len(calls) == 1
        else:
            assert calls[-1].operation == 'recover'
            futures[-1].set_result(SimpleNamespace(success=True))
            pi.gate.recover.assert_called_once()
            assert pi.recovery_deadline is None
    assert all(r.operation in ('clear_errors', 'recover') for r in calls)
    if outcome in ('send_failure', 'superseded') or outcome == 'persistent' and hold_healthy:
        pi.gate.recover.assert_not_called()
