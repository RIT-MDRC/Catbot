"""ROS adapter on ROS Python; inference uses an independent CPU or CUDA worker."""

from __future__ import annotations

import json
import math
import queue
import resource
import time
from collections import deque
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from catbot_interfaces.msg import (
    ActuatorPositionCommand,
    PolicyAction,
    PolicyActionAck,
    PolicyFeedback,
    PolicyMetrics,
    PolicyReady,
)
from catbot_policy.artifacts import available_models, resolve_downloaded
from catbot_policy.configuration import POLICY_DEFAULTS, POLICY_PARAMETERS
from catbot_policy.protocol import FEEDBACK_FIELDS, finite_values, validate_feedback
from catbot_policy.recording import SourceJournal
from catbot_policy.worker_client import WorkerClient


class PolicyNode(Node):
    def __init__(self):
        super().__init__("catbot_policy")

        self.policy_parameters = {
            name: self.declare_parameter(name, POLICY_DEFAULTS[name]).value
            for name in POLICY_PARAMETERS
        }
        self.action_session = str(self.declare_parameter("action_session", "").value)
        if not self.policy_parameters["simulation_mode"] and not self.action_session:
            raise ValueError(
                "Hardware policy must be started through Orin Supervisor (action_session required)"
            )

        self.supervised = bool(
            self.declare_parameter(
                "supervised_actions",
                not bool(self.policy_parameters["simulation_mode"]),
            ).value
        )
        self.requires_contract = bool(
            self.declare_parameter(
                "require_provider_contract",
                bool(self.policy_parameters["simulation_mode"]),
            ).value
        )
        self.provider_contract_topic = str(
            self.declare_parameter(
                "provider_contract_topic", "/simulation/contract"
            ).value
        )
        self.ready_publisher = self.create_publisher(
            PolicyReady,
            "/orin/policy/ready",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self._publish_ready(False, "loading")
        try:
            self._load()
        except BaseException as error:
            self._publish_ready(False, str(error))
            raise

    def _publish_ready(self, ready, detail):
        worker = getattr(self, "worker", None)
        report = worker.ready if worker is not None else {}
        verified = report.get("verified") is True
        self.ready_publisher.publish(
            PolicyReady(
                stamp=self.get_clock().now().to_msg(),
                session=self.action_session,
                bundle_id=str(report.get("bundle_id", "")),
                verified=verified,
                ready=bool(ready and verified),
                detail=detail,
            )
        )

    def _load(self):
        def param(name):
            return self.policy_parameters[name]

        bundle = str(param("policy_bundle"))
        if param("run_id") or param("checkpoint") or not bundle:
            selected = resolve_downloaded(
                param("policy_artifacts_directory"),
                param("run_id"),
                param("checkpoint"),
                entity=param("policy_entity"),
                project=param("policy_project"),
            )
            bundle = str(selected / "bundle")
        mapping = str(param("mapping_file"))
        if not (Path(bundle).expanduser() / "policy.json").is_file():
            raise ValueError(
                f"Missing policy bundle: {bundle}\n{available_models(param('policy_artifacts_directory'))}"
            )
        self.feedback_timeout = float(param("feedback_timeout"))
        self.worker_timeout = float(param("policy_worker_timeout"))
        startup_timeout = float(param("policy_startup_timeout"))
        if not all(
            math.isfinite(v) and v > 0
            for v in (self.feedback_timeout, self.worker_timeout, startup_timeout)
        ):
            raise ValueError("Policy timeouts must be positive and finite")
        self.worker = WorkerClient(
            str(param("policy_worker_project")),
            str(param("policy_python")),
            str(param("policy_uv_executable")),
            str(Path(bundle).expanduser()),
            str(Path(mapping).expanduser()) if mapping else "",
            self.feedback_timeout,
            self.worker_timeout,
            startup_timeout,
            device=str(param("policy_device")),
            environment=str(param("policy_worker_environment")),
            sync=str(param("policy_worker_sync")),
            torch_compatibility=str(param("policy_torch_compatibility")),
        )
        try:
            self.initialize()
        except BaseException:
            self.worker.close()
            raise

    def initialize(self):
        directory = str(self.declare_parameter("recording_directory", "").value)
        self.journal = (
            SourceJournal(
                directory,
                {
                    "session": self.action_session,
                    "worker": self.worker.ready,
                    "parameters": self.policy_parameters,
                },
            )
            if directory
            else None
        )
        self.recording_status = self.create_publisher(
            String, "/policy/recording/status", 1
        )
        ready = self.worker.ready
        self.metadata, self.mapping = ready["metadata"], ready["mapping"]
        self.dt = float(ready["dt"])
        if not math.isfinite(self.dt) or self.dt <= 0:
            raise ValueError("Invalid policy control interval")
        self.feedback = None
        self.received = float("-inf")
        self.epoch = 0
        self.command = [0.0, 0.0, 0.0]
        self.pending = None
        self.sequence = 0
        self.contract_ready = not self.requires_contract
        self.action_sequence = 0
        reliable = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.publisher = self.create_publisher(
            PolicyAction if self.supervised else ActuatorPositionCommand,
            "/orin/policy/action" if self.supervised else "/body/control/position",
            reliable,
        )
        if self.supervised:
            self.create_subscription(
                PolicyActionAck, "/rpi/supervisor/action_ack", self.action_ack, reliable
            )
        self.metrics = self.create_publisher(PolicyMetrics, "/policy/metrics", 1)
        self.create_subscription(
            PolicyFeedback,
            "/policy/feedback",
            self.feedback_callback,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        self.create_subscription(
            Twist, "/policy/cmd_vel", self.command_callback, reliable
        )
        self.create_subscription(
            String,
            self.provider_contract_topic,
            self.contract_callback,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.samples = deque(maxlen=10000)
        self.published = 0
        self.discarded = 0
        self.busy_ticks = 0
        self.last_tick = None
        self.missed = 0
        self.metrics_started = time.monotonic()
        self.adapter_cpu_started = time.process_time()
        self.worker_cpu = None
        self.worker_cpu_previous = None
        self.worker_rss = None
        self.create_timer(self.dt, self.tick)
        self.create_timer(0.002, self.poll)
        self.create_timer(5.0, self.report_metrics)
        self._publish_ready(
            self.contract_ready,
            "ready" if self.contract_ready else "waiting for provider contract",
        )
        self.get_logger().info(
            f"Policy worker ready on Python {self.worker.ready['python_version']}, device {self.worker.ready['device']}; ROS stays on its own interpreter"
        )

    def contract_callback(self, message):
        if not self.requires_contract:
            return
        value = json.loads(message.data)
        if (
            value.get("version") != 1
            or value.get("model_sha256") != self.metadata["model_sha256"]
            or value.get("policy_contract") != self.metadata["policy_contract"]
            or value.get("settings") != self.metadata["settings"]
            or value.get("mapping") != self.mapping
        ):
            self.contract_ready = False
            self._publish_ready(False, "provider contract mismatch")
            raise ValueError(
                "Provider model, policy contract, settings or mapping mismatch"
            )
        self.contract_ready = True
        self._publish_ready(True, "ready")

    def feedback_callback(self, message):
        if not self.contract_ready:
            return
        try:
            values = {}
            for name, _ in FEEDBACK_FIELDS:
                raw = getattr(message, name)
                if name == "motion_progress":
                    values[name] = float(raw)
                elif name in ("previous_contact", "has_stance"):
                    values[name] = [bool(value) for value in raw]
                else:
                    values[name] = [float(value) for value in raw]
            self.feedback = validate_feedback(values)
            if getattr(self, "journal", None) is not None:
                self.journal.submit(
                    "feedback",
                    {
                        "stamp": {
                            "sec": message.stamp.sec,
                            "nanosec": message.stamp.nanosec,
                        },
                        "values": self.feedback,
                    },
                )
            self.received = time.monotonic()
        except (KeyError, TypeError, ValueError) as error:
            self.feedback = None
            self.epoch += 1
            self.get_logger().error(f"Rejected feedback: {error}")

    def command_callback(self, message):
        try:
            self.command = finite_values(
                [message.linear.x, message.linear.y, message.angular.z], 3, "command"
            )
        except ValueError as error:
            self.get_logger().error(str(error))

    def tick(self):
        now = time.monotonic()
        if self.last_tick is not None:
            self.missed += max(0, int((now - self.last_tick) / self.dt + 0.1) - 1)
        self.last_tick = now
        if self.pending is not None:
            self.busy_ticks += 1
            return
        if (
            not self.contract_ready
            or self.feedback is None
            or not 0 <= now - self.received <= self.feedback_timeout
        ):
            return
        self.sequence += 1
        self.pending = {
            "id": self.sequence,
            "started": now,
            "received": self.received,
            "epoch": self.epoch,
            "accepted": False,
            "action_seen": False,
            "stamp": self.get_clock().now().to_msg(),
        }
        self.worker.send(
            {
                "type": "step",
                "id": self.sequence,
                "feedback": self.feedback,
                "feedback_received": self.received,
                "command": self.command,
            }
        )

    def poll(self):
        now = time.monotonic()
        if (
            self.pending is not None
            and now - self.pending["started"] > self.worker_timeout
        ):
            raise RuntimeError(
                "Policy worker stalled; restart the full session to reset history"
            )
        while True:
            try:
                result = self.worker.events.get_nowait()
            except queue.Empty:
                return
            if result.get("type") == "error":
                raise RuntimeError(result["error"])
            pending = self.pending
            if pending is None or result.get("id") != pending["id"]:
                raise RuntimeError("Unexpected policy worker response")
            if result["type"] == "action":
                if pending["action_seen"]:
                    raise RuntimeError("Duplicate policy action")
                pending["action_seen"] = True
                names = result["actuator_names"]
                targets = finite_values(result["positions_degrees"], 12, "targets")
                if names != self.mapping["actuator_names"] or any(
                    value < lo - 1e-5 or value > hi + 1e-5
                    for value, lo, hi in zip(
                        targets,
                        self.mapping["minimum_degrees"],
                        self.mapping["maximum_degrees"],
                        strict=True,
                    )
                ):
                    raise ValueError("Worker returned an invalid actuator command")
                # Float32 tensor limits may round slightly past JSON decimal bounds.
                targets = [
                    float(min(hi, max(lo, value)))
                    for value, lo, hi in zip(
                        targets,
                        self.mapping["minimum_degrees"],
                        self.mapping["maximum_degrees"],
                        strict=True,
                    )
                ]
                inference = float(result["inference_seconds"])
                if not math.isfinite(inference) or inference < 0:
                    raise ValueError("Invalid inference timing")
                now = time.monotonic()
                accepted = (
                    self.contract_ready
                    and self.feedback is not None
                    and self.epoch == pending["epoch"]
                    and 0 <= now - pending["received"] <= self.feedback_timeout
                )
                if getattr(self, "journal", None) is not None:
                    self.journal.submit(
                        "action",
                        {
                            "id": pending["id"],
                            "accepted": accepted,
                            "actuator_names": names,
                            "positions_degrees": targets,
                        },
                    )
                if accepted:
                    message = ActuatorPositionCommand()
                    message.actuator_names, message.positions_degrees = names, targets
                    if self.supervised:
                        self.action_sequence += 1
                        pending["gate_sequence"] = self.action_sequence
                        pending["gate_acknowledged"] = False
                        self.publisher.publish(
                            PolicyAction(
                                stamp=pending["stamp"],
                                session=self.action_session,
                                sequence=self.action_sequence,
                                command=message,
                            )
                        )
                    else:
                        self.publisher.publish(message)
                    sample = (
                        inference * 1000,
                        (time.monotonic() - pending["started"]) * 1000,
                        (now - pending["received"]) * 1000,
                    )
                    pending["sample"] = sample
                    if not self.supervised:
                        pending["accepted"] = True
                        self.published += 1
                        self.samples.append(sample)
                else:
                    self.discarded += 1
                if not (self.supervised and accepted):
                    self.worker.send(
                        {"type": "ack", "id": pending["id"], "published": accepted}
                    )
            elif result["type"] == "done":
                if result["published"] != pending["accepted"]:
                    raise RuntimeError("Policy action-history acknowledgement mismatch")
                if not pending["action_seen"] and not result["published"]:
                    self.discarded += 1
                self.worker_cpu = result.get("cpu_seconds", self.worker_cpu)
                self.worker_rss = result.get("peak_rss_kib", self.worker_rss)
                self.pending = None
            else:
                raise RuntimeError("Unknown policy worker response")

    def action_ack(self, message):
        pending = self.pending
        if (
            message.session != self.action_session
            or pending is None
            or message.sequence != pending.get("gate_sequence")
            or pending.get("gate_acknowledged")
        ):
            return
        if getattr(self, "journal", None) is not None:
            self.journal.submit(
                "action_ack",
                {"sequence": message.sequence, "forwarded": message.forwarded},
            )
        pending["gate_acknowledged"] = True
        pending["accepted"] = message.forwarded
        if message.forwarded:
            self.published += 1
            self.samples.append(pending["sample"])
        else:
            self.discarded += 1
        self.worker.send(
            {"type": "ack", "id": pending["id"], "published": message.forwarded}
        )

    def report_metrics(self):
        elapsed = time.monotonic() - self.metrics_started

        def percentiles(values):
            values = sorted(values)
            return {
                label: values[int((len(values) - 1) * q)] if values else math.nan
                for label, q in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))
            }

        report = {
            "stamp": self.get_clock().now().to_msg(),
            "adapter_cpu_percent_one_core": 100
            * (time.process_time() - self.adapter_cpu_started)
            / elapsed,
            "adapter_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "device": self.worker.ready["device"],
            "window_seconds": elapsed,
            "control_interval_ms": self.dt * 1000,
            "published_hz": self.published / elapsed,
            "sample_count": len(self.samples),
            "missed_timer_intervals": self.missed,
            "busy_ticks": self.busy_ticks,
            "discarded_results": self.discarded,
            "worker_peak_rss_kib": float(self.worker_rss)
            if self.worker_rss is not None
            else math.nan,
            "worker_cpu_percent_one_core": math.nan
            if self.worker_cpu is None or self.worker_cpu_previous is None
            else 100 * (self.worker_cpu - self.worker_cpu_previous) / elapsed,
        }
        for prefix, index in (("inference", 0), ("round_trip", 1), ("feedback_age", 2)):
            for percentile, value in percentiles(
                [s[index] for s in self.samples]
            ).items():
                report[f"{prefix}_{percentile}_ms"] = value
        self.metrics.publish(PolicyMetrics(**report))
        if getattr(self, "journal", None) is not None and (
            self.journal.dropped or self.journal.error
        ):
            self.get_logger().warning(
                f"Source recording dropped={self.journal.dropped}: {self.journal.error}"
            )
        if (
            getattr(self, "recording_status", None) is not None
            and self.journal is not None
        ):
            self.recording_status.publish(
                String(data=json.dumps(self.journal.status()))
            )
        self.worker_cpu_previous = self.worker_cpu
        self.samples.clear()
        self.published = self.discarded = self.busy_ticks = self.missed = 0
        self.metrics_started = time.monotonic()
        self.adapter_cpu_started = time.process_time()

    def destroy_node(self):
        self.worker.close()
        if getattr(self, "journal", None) is not None:
            self.journal.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = PolicyNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
