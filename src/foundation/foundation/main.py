"""Catbot ROS node for sparse, position-controlled body actuation."""

import os
import time
from dataclasses import dataclass, field

import rclpy
from body_control import actuator_names_by_axis_id, prepare_position_targets
from body_state import flag_messages, heartbeat_available, kinematic_values
from component.actuator import actuator_actions
from component.can import can_actions
from component.motor import motor_actions
from component.motor.odrive_enums import (
    AxisError,
    ControllerError,
    EncoderError,
    MotorError,
    MotorState,
    SensorlessError,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from state_management import configure_device
from std_msgs.msg import Empty

from catbot_interfaces.msg import (
    ActuatorErrorState,
    ActuatorKinematicState,
    ActuatorPositionCommand,
    BodyErrorState,
    BodyKinematicState,
)

HEARTBEAT_TIMEOUT_SECONDS = 3.0
OPERATION_TIMEOUT_SECONDS = 30.0
CONTROL_TIMER_PERIOD_SECONDS = 0.05
POSITION_STATE_PERIOD_SECONDS = 0.02
STATE_CHECK_PERIOD_SECONDS = 0.05
HEARTBEAT_STALE_SECONDS = 0.5
ENCODER_STALE_SECONDS = 0.25
ERROR_REQUEST_PERIOD_SECONDS = 1.0


@dataclass
class MotorSequence:
    """Track one non-blocking all-motor maintenance operation."""

    label: str
    requested_state: MotorState | None
    motor_names: list[str]
    phase: str = "waiting_for_idle"
    index: int = 0
    current_name: str | None = None
    deadline: float = 0.0
    failures: set[str] = field(default_factory=set)


class BodyControlNode(Node):
    """Receive body commands and coordinate configured ODrive motors."""

    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), "pinconfig.json")
        configure_device(config_path)
        super().__init__("foundation_node")

        self.actuator_names = actuator_actions.get_names()
        self.ordered_motor_names = actuator_names_by_axis_id(self.actuator_names)
        self.ready_motor_names: set[str] = set()
        self.sequence: MotorSequence | None = None
        self.startup_deadline = time.monotonic() + HEARTBEAT_TIMEOUT_SECONDS
        self.startup_sequence_queued = False
        self.last_error_snapshot = None
        self.last_error_request_times = {}

        position_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.create_subscription(
            ActuatorPositionCommand,
            "/body/control/position",
            self._position_callback,
            position_qos,
        )
        position_state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        error_state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.position_state_publisher = self.create_publisher(
            BodyKinematicState,
            "/body/state/position",
            position_state_qos,
        )
        self.error_state_publisher = self.create_publisher(
            BodyErrorState,
            "/body/state/error",
            error_state_qos,
        )
        self.create_subscription(
            Empty,
            "/body/control/script/home",
            lambda _: self._queue_script("homing", MotorState.HOMING),
            10,
        )
        self.create_subscription(
            Empty,
            "/body/control/script/full_calibrate",
            lambda _: self._queue_script(
                "full calibration", MotorState.FULL_CALIBRATION_SEQUENCE
            ),
            10,
        )
        self.create_subscription(
            Empty,
            "/body/control/script/calibrate",
            lambda _: self._queue_script(
                "motor calibration", MotorState.MOTOR_CALIBRATION
            ),
            10,
        )
        self.create_subscription(
            Empty,
            "/body/control/script/clear_errors",
            lambda _: self._queue_script("clear errors", None),
            10,
        )
        self.create_timer(CONTROL_TIMER_PERIOD_SECONDS, self._control_tick)
        self.create_timer(POSITION_STATE_PERIOD_SECONDS, self._publish_position_state)
        self.create_timer(STATE_CHECK_PERIOD_SECONDS, self._update_error_state)

        for name in self.ordered_motor_names:
            if not motor_actions.clear_error_message(name):
                self.get_logger().error(f"Failed to send startup error clear to {name}")
        self.get_logger().warning(
            "Startup motor calibration can move hardware; keep the mechanism clear."
        )

    def _responsive_motor_names(self) -> list[str]:
        return [
            name
            for name in self.ordered_motor_names
            if motor_actions.get_state_snapshot(name).current_state
            != MotorState.UNDEFINED
        ]

    def _publish_position_state(self) -> None:
        now = time.monotonic()
        message = BodyKinematicState()
        message.stamp = self.get_clock().now().to_msg()
        for name in self.ordered_motor_names:
            motor = motor_actions.get_state_snapshot(name)
            valid, position, velocity = kinematic_values(name, now, ENCODER_STALE_SECONDS)
            actuator = ActuatorKinematicState()
            actuator.actuator_name = name
            actuator.axis_id = motor.axis_id
            actuator.valid = valid
            actuator.position_degrees = position
            actuator.velocity_degrees_per_second = velocity
            message.actuators.append(actuator)
        self.position_state_publisher.publish(message)

    def _update_error_state(self) -> None:
        now = time.monotonic()
        message = BodyErrorState()
        message.stamp = self.get_clock().now().to_msg()
        snapshot = []
        for name in self.ordered_motor_names:
            motor = motor_actions.get_state_snapshot(name)
            heartbeat_ok = heartbeat_available(motor, now, HEARTBEAT_STALE_SECONDS)
            ready = (
                heartbeat_ok
                and name in self.ready_motor_names
                and motor.current_state == MotorState.CLOSED_LOOP_CONTROL
            )
            axis_messages = flag_messages(motor.axis_error, AxisError)
            motor_messages = flag_messages(motor.motor_error, MotorError)
            encoder_messages = flag_messages(motor.encoder_error, EncoderError)
            sensorless_messages = flag_messages(motor.sensorless_error, SensorlessError)
            controller_messages = flag_messages(motor.controller_error, ControllerError)

            actuator = ActuatorErrorState()
            actuator.actuator_name = name
            actuator.axis_id = motor.axis_id
            actuator.heartbeat_available = heartbeat_ok
            actuator.ready = ready
            actuator.axis_state = int(motor.current_state)
            actuator.axis_error_flags = motor.axis_error
            actuator.axis_error_messages = axis_messages
            actuator.motor_error_flags = motor.motor_error
            actuator.motor_error_messages = motor_messages
            actuator.encoder_error_flags = motor.encoder_error
            actuator.encoder_error_messages = encoder_messages
            actuator.sensorless_error_flags = motor.sensorless_error
            actuator.sensorless_error_messages = sensorless_messages
            actuator.controller_error_flags = motor.controller_error
            actuator.controller_error_messages = controller_messages
            message.actuators.append(actuator)

            snapshot.append(
                (
                    name,
                    motor.axis_id,
                    heartbeat_ok,
                    ready,
                    int(motor.current_state),
                    motor.axis_error,
                    tuple(axis_messages),
                    motor.motor_error,
                    tuple(motor_messages),
                    motor.encoder_error,
                    tuple(encoder_messages),
                    motor.sensorless_error,
                    tuple(sensorless_messages),
                    motor.controller_error,
                    tuple(controller_messages),
                )
            )

            has_detailed_error = any(
                (
                    motor.motor_error_flag,
                    motor.encoder_error_flag,
                    motor.sensorless_error_flag,
                    motor.controller_error_flag,
                )
            )
            last_request = self.last_error_request_times.get(name, float("-inf"))
            if (
                has_detailed_error
                and now - last_request >= ERROR_REQUEST_PERIOD_SECONDS
            ):
                if not motor_actions.request_error_details(name):
                    self.get_logger().error(
                        f"Failed to request detailed errors from {name}"
                    )
                self.last_error_request_times[name] = now

        snapshot = tuple(snapshot)
        if snapshot != self.last_error_snapshot:
            self.error_state_publisher.publish(message)
            self.last_error_snapshot = snapshot

    def _position_callback(self, message: ActuatorPositionCommand) -> None:
        try:
            targets = prepare_position_targets(
                list(message.actuator_names),
                list(message.positions_degrees),
                self.actuator_names,
                self.ready_motor_names,
            )
            for name, _ in targets:
                motor = motor_actions.get_state_snapshot(name)
                if motor.current_state != MotorState.CLOSED_LOOP_CONTROL:
                    self.ready_motor_names.discard(name)
                    raise ValueError(
                        f'Actuator "{name}" is no longer in closed-loop control'
                    )
        except ValueError as error:
            self.get_logger().error(f"Rejected position command: {error}")
            return

        failed = []
        for name, target_degrees in targets:
            if not actuator_actions.set_target_position(name, target_degrees):
                failed.append(name)
        if failed:
            self.get_logger().error(
                "Failed to send position targets to: " + ", ".join(failed)
            )

    def _queue_script(self, label: str, requested_state: MotorState | None) -> None:
        if self.sequence is not None:
            self.get_logger().warning(
                f'Ignoring "{label}" because "{self.sequence.label}" is still active'
            )
            return
        motor_names = self._responsive_motor_names()
        if not motor_names:
            self.get_logger().error(f'Cannot start "{label}": no motor heartbeats')
            return
        self._start_sequence(label, requested_state, motor_names)

    def _start_sequence(
        self,
        label: str,
        requested_state: MotorState | None,
        motor_names: list[str],
    ) -> None:
        self.ready_motor_names.difference_update(motor_names)
        sequence = MotorSequence(label, requested_state, motor_names)
        sequence.deadline = time.monotonic() + HEARTBEAT_TIMEOUT_SECONDS
        self.sequence = sequence
        for name in motor_names:
            if not motor_actions.set_axis_state(name, MotorState.IDLE):
                sequence.failures.add(name)
        self.get_logger().info(f'Started "{label}" for {len(motor_names)} motor(s)')

    def _control_tick(self) -> None:
        now = time.monotonic()
        if not self.startup_sequence_queued:
            if now < self.startup_deadline and any(
                motor.current_state == MotorState.UNDEFINED
                for name in self.ordered_motor_names
                for motor in (motor_actions.get_state_snapshot(name),)
            ):
                return
            responsive = self._responsive_motor_names()
            missing = [
                name
                for name in self.ordered_motor_names
                if motor_actions.get_state_snapshot(name).current_state
                == MotorState.UNDEFINED
            ]
            if missing:
                self.get_logger().error(
                    "No startup heartbeat from: " + ", ".join(missing)
                )
            self.startup_sequence_queued = True
            if responsive:
                self._start_sequence(
                    "startup motor calibration",
                    MotorState.MOTOR_CALIBRATION,
                    responsive,
                )
            else:
                self.get_logger().error("No ODrive motors available at startup")
            return

        sequence = self.sequence
        if sequence is None:
            return

        if sequence.phase == "waiting_for_idle":
            waiting = [
                name
                for name in sequence.motor_names
                if name not in sequence.failures
                and motor_actions.get_state_snapshot(name).current_state
                != MotorState.IDLE
            ]
            if waiting and now < sequence.deadline:
                return
            if waiting:
                sequence.failures.update(waiting)
                self.get_logger().error("Timed out disarming: " + ", ".join(waiting))
            if sequence.requested_state is None:
                for name in sequence.motor_names:
                    if (
                        name not in sequence.failures
                        and not motor_actions.clear_error_message(name)
                    ):
                        sequence.failures.add(name)
                sequence.phase = "waiting_for_errors_to_clear"
                sequence.deadline = now + HEARTBEAT_TIMEOUT_SECONDS
            else:
                sequence.phase = "starting_next"
            return

        if sequence.phase == "waiting_for_errors_to_clear":
            waiting = [
                name
                for name in sequence.motor_names
                if name not in sequence.failures
                and motor_actions.get_state_snapshot(name).axis_error
            ]
            if waiting and now < sequence.deadline:
                return
            if waiting:
                sequence.failures.update(waiting)
                self.get_logger().error(
                    "Errors remained after clear request: " + ", ".join(waiting)
                )
            sequence.phase = "arming_next"
            sequence.index = 0
            return

        if sequence.phase == "starting_next":
            while (
                sequence.index < len(sequence.motor_names)
                and sequence.motor_names[sequence.index] in sequence.failures
            ):
                sequence.index += 1
            if sequence.index >= len(sequence.motor_names):
                sequence.phase = "arming_next"
                sequence.index = 0
                return
            name = sequence.motor_names[sequence.index]
            sequence.current_name = name
            requested_state = sequence.requested_state
            if requested_state is None:
                raise RuntimeError("motor operation sequence is missing a state")
            if not motor_actions.set_axis_state(name, requested_state):
                sequence.failures.add(name)
                sequence.index += 1
                return
            sequence.phase = "waiting_for_operation_start"
            sequence.deadline = now + HEARTBEAT_TIMEOUT_SECONDS
            return

        if sequence.phase == "waiting_for_operation_start":
            name = sequence.current_name
            if name is None:
                raise RuntimeError("motor operation sequence is missing a motor")
            if motor_actions.get_state_snapshot(name).current_state == sequence.requested_state:
                sequence.phase = "waiting_for_operation_finish"
                sequence.deadline = now + OPERATION_TIMEOUT_SECONDS
            elif now >= sequence.deadline:
                sequence.failures.add(name)
                sequence.index += 1
                sequence.phase = "starting_next"
                self.get_logger().error(f"{name} did not start {sequence.label}")
            return

        if sequence.phase == "waiting_for_operation_finish":
            name = sequence.current_name
            if name is None:
                raise RuntimeError("motor operation sequence is missing a motor")
            motor = motor_actions.get_state_snapshot(name)
            if motor.current_state == MotorState.IDLE:
                if motor.axis_error:
                    sequence.failures.add(name)
                sequence.index += 1
                sequence.phase = "starting_next"
            elif now >= sequence.deadline:
                sequence.failures.add(name)
                motor_actions.set_axis_state(name, MotorState.IDLE)
                sequence.index += 1
                sequence.phase = "starting_next"
                self.get_logger().error(f"{name} timed out during {sequence.label}")
            return

        if sequence.phase == "arming_next":
            while (
                sequence.index < len(sequence.motor_names)
                and sequence.motor_names[sequence.index] in sequence.failures
            ):
                sequence.index += 1
            if sequence.index >= len(sequence.motor_names):
                self._finish_sequence(sequence)
                return
            name = sequence.motor_names[sequence.index]
            motor = motor_actions.get_state_snapshot(name)
            sequence.current_name = name
            if motor.axis_error or motor.current_position is None:
                sequence.failures.add(name)
                sequence.index += 1
                return
            commands_sent = (
                actuator_actions.configure_trajectory(name)
                and motor_actions.hold_current_position(name)
                and motor_actions.set_axis_state(name, MotorState.CLOSED_LOOP_CONTROL)
            )
            if not commands_sent:
                sequence.failures.add(name)
                sequence.index += 1
                return
            sequence.phase = "waiting_for_closed_loop"
            sequence.deadline = now + HEARTBEAT_TIMEOUT_SECONDS
            return

        if sequence.phase == "waiting_for_closed_loop":
            name = sequence.current_name
            if name is None:
                raise RuntimeError("motor operation sequence is missing a motor")
            motor = motor_actions.get_state_snapshot(name)
            if motor.current_state == MotorState.CLOSED_LOOP_CONTROL:
                self.ready_motor_names.add(name)
                sequence.index += 1
                sequence.phase = "arming_next"
            elif now >= sequence.deadline:
                sequence.failures.add(name)
                motor_actions.set_axis_state(name, MotorState.IDLE)
                sequence.index += 1
                sequence.phase = "arming_next"
                self.get_logger().error(f"{name} did not enter closed-loop control")

    def _finish_sequence(self, sequence: MotorSequence) -> None:
        if sequence.failures:
            self.get_logger().error(
                f'Finished "{sequence.label}" with failed motors: '
                + ", ".join(sorted(sequence.failures))
            )
        else:
            self.get_logger().info(f'Finished "{sequence.label}" successfully')
        self.sequence = None

    def shutdown_hardware(self) -> None:
        """Disarm motors and close CAN resources during every normal shutdown."""
        for name in self.ordered_motor_names:
            motor_actions.set_axis_state(name, MotorState.IDLE)
        self.ready_motor_names.clear()
        for bus_name in can_actions.get_names():
            try:
                can_actions.close(bus_name)
            except (OSError, ValueError) as error:
                self.get_logger().error(
                    "Unable to close CAN bus %s: %s", bus_name, error
                )


def main(args=None):
    """Run the Catbot body-control node."""
    rclpy.init(args=args)
    node = None
    try:
        node = BodyControlNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.shutdown_hardware()
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
