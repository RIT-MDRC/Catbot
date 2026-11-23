"""Catbot ROS node for sparse, position-controlled body actuation."""

import json
import os
import signal
import time

import rclpy
from body_control import (
    actuator_names_by_axis_id,
    prepare_position_targets,
    validate_motor_command,
)
from body_state import (
    encoder_available,
    flag_messages,
    heartbeat_available,
    kinematic_values,
)
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
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from state_management import configure_device
from tuning import validate_tuning

from catbot_interfaces.msg import (
    ActuatorErrorState,
    ActuatorKinematicState,
    ActuatorPositionCommand,
    BodyErrorState,
    BodyKinematicState,
)
from catbot_interfaces.srv import MotorCommand

POSITION_STATE_PERIOD_SECONDS = 0.02
STATE_CHECK_PERIOD_SECONDS = 0.05
HEARTBEAT_STALE_SECONDS = 0.5
ENCODER_STALE_SECONDS = 0.25
ERROR_REQUEST_PERIOD_SECONDS = 1.0


class BodyControlNode(Node):
    """Validate and perform immediate body I/O; the Pi owns all sequencing."""

    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), "pinconfig.json")
        configure_device(config_path)
        super().__init__("foundation_node")

        self.actuator_names = actuator_actions.get_names()
        self.motion_inhibited = False
        self.emergency_disarm = False
        self.ordered_motor_names = actuator_names_by_axis_id(self.actuator_names)
        self.last_error_request_times = {}
        self.invalid_kinematics = set()

        self.tuning = {"policy_gain_scale": 0.1}
        for name in self.actuator_names:
            self.tuning.update(
                {
                    f"{name}.speed_motor_turns_s": actuator_actions.get_trajectory_velocity_motor_turns(
                        name
                    ),
                    f"{name}.accel_motor_turns_s2": actuator_actions.get_trajectory_acceleration_motor_turns(
                        name
                    ),
                    f"{name}.position_gain": -1.0,
                    f"{name}.velocity_gain": -1.0,
                    f"{name}.integrator_gain": -1.0,
                }
            )
        self.tuning = {
            name: self.declare_parameter(name, float(value)).value
            for name, value in self.tuning.items()
        }
        validate_tuning(
            {name: value for name, value in self.tuning.items() if value != -1.0}
        )
        self.applied_gain_scale = 0.1
        self.gains_dirty = True
        self.add_on_set_parameters_callback(self._tune)
        self.create_timer(0.1, self._apply_gains)
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
        self.create_subscription(
            ActuatorPositionCommand,
            "/body/control/move/position",
            self._move_position_callback,
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
        self.create_service(MotorCommand, "/body/control/motor", self._motor_command)
        self.create_timer(POSITION_STATE_PERIOD_SECONDS, self._publish_position_state)
        self.create_timer(STATE_CHECK_PERIOD_SECONDS, self._update_error_state)

    def _ready_motor_names(self, *, allow_idle=False) -> set[str]:
        ready = set()
        for name in self.ordered_motor_names:
            motor = motor_actions.get_state_snapshot(name)
            # CAN updates run on another thread. Read the clock after capturing
            # state so a newly received estimate cannot appear to be in the future.
            now = time.monotonic()
            if self._motor_ready(name, motor, now, allow_idle=allow_idle):
                ready.add(name)
        return ready

    def _motor_ready(self, name, motor, now, *, allow_idle=False) -> bool:
        return (
            heartbeat_available(motor, now, HEARTBEAT_STALE_SECONDS)
            and motor.current_state
            in (
                (MotorState.IDLE, MotorState.CLOSED_LOOP_CONTROL)
                if allow_idle
                else (MotorState.CLOSED_LOOP_CONTROL,)
            )
            and not motor_actions.has_fault(motor)
            and encoder_available(motor, now, ENCODER_STALE_SECONDS)
            and kinematic_values(name, now, ENCODER_STALE_SECONDS, motor_state=motor)[0]
        )

    def _tune(self, parameters):
        updates = {p.name: p.value for p in parameters if p.name in self.tuning}
        try:
            validate_tuning(updates)
            proposed = {**self.tuning, **updates}
            if "policy_gain_scale" in updates and any(
                proposed[f"{axis}.{gain}_gain"] < 0
                for axis in self.actuator_names
                for gain in ("position", "velocity", "integrator")
            ):
                raise ValueError("Configure all per-axis gain baselines before scaling")
            for key, value in updates.items():
                axis, _, field = key.rpartition(".")
                if field == "speed_motor_turns_s":
                    if not actuator_actions.set_trajectory_speed(
                        axis, value, "motor_turns_per_second"
                    ):
                        raise ValueError(
                            f"CAN rejected {key}; earlier writes may have applied"
                        )
                elif (
                    field == "accel_motor_turns_s2"
                    and not actuator_actions.set_trajectory_acceleration(axis, value)
                ):
                    raise ValueError(
                        f"CAN rejected {key}; earlier writes may have applied"
                    )
            self.tuning = proposed
            self.gains_dirty = True
            self.get_logger().info("Runtime tuning: " + json.dumps(updates))
            return SetParametersResult(successful=True)
        except (ValueError, TypeError) as error:
            return SetParametersResult(successful=False, reason=str(error))

    def _apply_gains(self):
        target = self.tuning["policy_gain_scale"]
        scale = self.applied_gain_scale + max(
            -0.05, min(0.05, target - self.applied_gain_scale)
        )
        if not self.gains_dirty and scale == self.applied_gain_scale:
            return
        complete = True
        for axis in self.actuator_names:
            gains = [
                self.tuning[f"{axis}.{gain}_gain"]
                for gain in ("position", "velocity", "integrator")
            ]
            if any(value < 0 for value in gains):
                continue
            if not actuator_actions.set_controller_gains(
                axis, *(value * scale for value in gains)
            ):
                complete = False
                self.get_logger().error(f"CAN gain update failed: {axis}")
        if complete:
            self.applied_gain_scale = scale
            self.gains_dirty = False

    def _motor_command(self, request, response):
        names = list(request.actuator_names) or self.ordered_motor_names
        try:
            validate_motor_command(
                names, self.actuator_names, request.operation, request.state
            )
            if request.operation in ("emergency", "fault_stop", "recover") and set(
                names
            ) != set(self.actuator_names):
                raise ValueError("Stop/recovery requires the complete actuator roster")
            if request.operation == "emergency":
                self.motion_inhibited = True
                self.emergency_disarm = True
            if request.operation == "fault_stop":
                self.motion_inhibited = True
                # Never downgrade an explicit e-stop to a holding stop.
                keep = set() if self.emergency_disarm else self._ready_motor_names()
                failed = []
                for name in names:
                    sent = (
                        motor_actions.hold_after_fault(name)
                        if name in keep
                        else motor_actions.set_axis_state(name, MotorState.IDLE)
                    )
                    if not sent:
                        # Feedback may have changed since the readiness snapshot.
                        motor_actions.set_axis_state(name, MotorState.IDLE)
                        failed.append(name)
                response.success = not failed
                response.message = (
                    "motion inhibited; healthy closed-loop axes retained"
                    if not failed
                    else "Send failed: " + ", ".join(failed)
                )
                return response
            if request.operation == "recover":
                allow_hold = not self.emergency_disarm
                ready = self._ready_motor_names() if allow_hold else set()
                if any(
                    not heartbeat_available(
                        motor_actions.get_state_snapshot(name),
                        time.monotonic(),
                        HEARTBEAT_STALE_SECONDS,
                    )
                    or (
                        motor_actions.get_state_snapshot(name).current_state
                        != MotorState.IDLE
                        and name not in ready
                    )
                    or (
                        allow_hold
                        and motor_actions.has_fault(
                            motor_actions.get_state_snapshot(name)
                        )
                    )
                    for name in names
                ):
                    raise ValueError(
                        "Recovery requires fresh stopped axes; clear actuator faults first"
                    )
                self.motion_inhibited = False
                self.emergency_disarm = False
                response.success, response.message = (
                    True,
                    "motion latch cleared; axis states and targets unchanged",
                )
                return response
            if self.motion_inhibited and (
                request.operation == "hold"
                or (
                    request.operation == "state"
                    and request.state != int(MotorState.IDLE)
                )
            ):
                raise ValueError("Motion inhibited by emergency; recover first")
            # Validate the entire batch before issuing any non-idle operation.
            for name in names:
                motor = motor_actions.get_state_snapshot(name)
                if request.operation not in ("idle", "emergency", "clear_errors"):
                    if not heartbeat_available(
                        motor, time.monotonic(), HEARTBEAT_STALE_SECONDS
                    ):
                        raise ValueError(f"No fresh heartbeat for {name}")
                    if motor_actions.has_fault(motor):
                        raise ValueError(f"Axis fault on {name}")
                    needs_encoder = request.operation in ("hold", "trajectory") or (
                        request.operation == "state"
                        and request.state == int(MotorState.CLOSED_LOOP_CONTROL)
                    )
                    if needs_encoder and not encoder_available(
                        motor, time.monotonic(), ENCODER_STALE_SECONDS
                    ):
                        raise ValueError(f"No fresh encoder for {name}")
            failed = []
            for name in names:
                if request.operation in ("idle", "emergency"):
                    sent = motor_actions.set_axis_state(name, MotorState.IDLE)
                elif request.operation == "clear_errors":
                    sent = motor_actions.clear_error_message(name)
                elif request.operation == "trajectory":
                    sent = actuator_actions.configure_trajectory(name)
                elif request.operation == "hold":
                    sent = motor_actions.hold_current_position(name)
                else:
                    sent = motor_actions.set_axis_state(name, MotorState(request.state))
                if not sent:
                    failed.append(name)
            response.success = not failed
            response.message = (
                "sent" if not failed else "Send failed: " + ", ".join(failed)
            )
        except ValueError as error:
            response.success = False
            response.message = str(error)
        return response

    def _publish_position_state(self) -> None:
        message = BodyKinematicState()
        message.stamp = self.get_clock().now().to_msg()
        invalid_kinematics = set()
        for name in self.ordered_motor_names:
            motor = motor_actions.get_state_snapshot(name)
            now = time.monotonic()
            valid, position, velocity = kinematic_values(
                name, now, ENCODER_STALE_SECONDS, motor_state=motor
            )
            if not valid and encoder_available(motor, now, ENCODER_STALE_SECONDS):
                invalid_kinematics.add(name)
                if name not in self.invalid_kinematics:
                    self.get_logger().error(
                        f'Actuator "{name}" encoder feedback cannot be converted '
                        f"to logical coordinates: position={motor.current_position} "
                        f"motor turns, velocity={motor.current_velocity} turns/s; "
                        "publishing invalid feedback. Check encoder zero and motion profile."
                    )
            actuator = ActuatorKinematicState()
            actuator.actuator_name = name
            actuator.axis_id = motor.axis_id
            actuator.valid = valid
            actuator.position_degrees = position
            actuator.velocity_degrees_per_second = velocity
            message.actuators.append(actuator)
        self.invalid_kinematics = invalid_kinematics
        self.position_state_publisher.publish(message)

    def _update_error_state(self) -> None:
        message = BodyErrorState()
        message.stamp = self.get_clock().now().to_msg()
        for name in self.ordered_motor_names:
            motor = motor_actions.get_state_snapshot(name)
            now = time.monotonic()
            heartbeat_ok = heartbeat_available(motor, now, HEARTBEAT_STALE_SECONDS)
            ready = self._motor_ready(name, motor, now)
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

        self.error_state_publisher.publish(message)

    def _move_position_callback(self, message: ActuatorPositionCommand) -> None:
        self._position_callback(message, auto_arm=True)

    def _position_callback(
        self, message: ActuatorPositionCommand, *, auto_arm=False
    ) -> None:
        try:
            if self.motion_inhibited:
                raise ValueError("Motion inhibited by emergency; recover first")
            targets = prepare_position_targets(
                list(message.actuator_names),
                list(message.positions_degrees),
                self.actuator_names,
                self._ready_motor_names(allow_idle=auto_arm),
            )
            for name, _ in targets:
                motor = motor_actions.get_state_snapshot(name)
                if motor.current_state not in (
                    (MotorState.IDLE, MotorState.CLOSED_LOOP_CONTROL)
                    if auto_arm
                    else (MotorState.CLOSED_LOOP_CONTROL,)
                ):
                    raise ValueError(
                        f'Actuator "{name}" is no longer in closed-loop control'
                    )
        except ValueError as error:
            self.get_logger().error(f"Rejected position command: {error}")
            return

        failed = []
        for name, target_degrees in targets:
            if not actuator_actions.set_target_position(
                name, target_degrees, auto_arm=auto_arm
            ):
                failed.append(name)
                break
        if failed:
            for name, _ in targets:
                motor_actions.set_axis_state(name, MotorState.IDLE)
            self.get_logger().error(
                "Failed to send position targets to: " + ", ".join(failed)
            )

    def shutdown_hardware(self) -> None:
        """Disarm motors and close CAN resources during every normal shutdown."""
        for name in self.ordered_motor_names:
            motor_actions.set_axis_state(name, MotorState.IDLE)
        for bus_name in can_actions.get_names():
            try:
                can_actions.close(bus_name)
            except (OSError, ValueError) as error:
                self.get_logger().error(
                    "Unable to close CAN bus %s: %s", bus_name, error
                )


def main(args=None):
    """Run the Catbot body-control node."""
    # Keep ROS usable until hardware cleanup finishes, including on launch SIGTERM.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    handlers = {
        sig: signal.signal(sig, signal.default_int_handler)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    node = None
    try:
        node = BodyControlNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if node is not None:
                try:
                    node.shutdown_hardware()
                finally:
                    node.destroy_node()
        finally:
            try:
                rclpy.try_shutdown()
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)


if __name__ == "__main__":
    main()
