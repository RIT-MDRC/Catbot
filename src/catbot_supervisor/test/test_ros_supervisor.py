"""Real ROS adapters and a managed policy worker; Foundation hardware is doubled."""

import json
import time
from pathlib import Path

import pytest
import rclpy
from catbot_supervisor.core import Mode
from catbot_supervisor.node import RpiSupervisor
from catbot_supervisor.orin import OrinSupervisor
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_srvs.srv import Trigger

from catbot_interfaces.msg import (
    ActuatorErrorState,
    ActuatorPositionCommand,
    BodyErrorState,
    PolicyFeedback,
)
from catbot_interfaces.srv import MotorCommand, RunScript

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
        body = Node("supervisor_test_body", use_global_arguments=False)
        states = dict.fromkeys(names, 1)
        operations, received, completing = [], [], {}
        state_pub = body.create_publisher(
            BodyErrorState,
            "/body/state/error",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        feedback_pub = body.create_publisher(PolicyFeedback, "/policy/feedback", 1)
        sensors_enabled = [True]

        def motor(request, response):
            operations.append(
                (request.operation, request.state, list(request.actuator_names))
            )
            for name in request.actuator_names or names:
                if request.operation == "idle":
                    states[name] = 1
                    completing.pop(name, None)
                elif request.operation == "state":
                    states[name] = request.state
                    if request.state == 4:
                        completing[name] = time.monotonic() + 0.15
            response.success, response.message = True, "sent"
            return response

        body.create_service(MotorCommand, "/body/control/motor", motor)
        body.create_subscription(
            ActuatorPositionCommand, "/body/control/position", received.append, 1
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
                        )
                        for index, name in enumerate(names)
                    ],
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

        until(lambda: pi.gate.mode == Mode.IDLE)
        assert not received and not orin.jobs.running("policy")
        call(RunScript, "/rpi/supervisor/script", RunScript.Request(name="startup"))
        until(lambda: pi.gate.mode == Mode.READY, timeout=30)
        assert not received, "Policy proposals must not cross the gate before RUNNING"
        assert orin.jobs.running("policy")
        assert [
            names_
            for operation, state, names_ in operations
            if operation == "state" and state == 4
        ] == [[name] for name in names]
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
        assert pi.gate.mode == Mode.IDLE
        assert len(received) == count
        call(RunScript, "/rpi/supervisor/script", RunScript.Request(name="shutdown"))
        until(lambda: not pi.runner.active)
        assert pi.gate.mode == Mode.SHUTDOWN
    finally:
        executor.shutdown()
        for node in (pi, orin, body):
            if node is not None:
                node.destroy_node()
        rclpy.shutdown()
