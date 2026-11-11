"""Logical actuator state and motor-boundary actions."""

import math
from dataclasses import dataclass, field

from state_management import (
    create_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from ..motor import motor_actions
from ..motor.odrive_enums import ControlMode, InputMode
from . import motion_profile as profile_actions


@device
@dataclass
class Actuator:
    """One ODrive motor governed by one reusable motion profile."""

    motor: motor_actions.ODriveMotor = identifier(motor_actions.ctx)  # noqa: RUF009
    profile: profile_actions.ActuatorMotionProfile = identifier(  # noqa: RUF009
        profile_actions.ctx
    )
    trajectory_velocity_motor_turns: float = field(init=False)
    trajectory_acceleration_motor_turns: float = field(init=False)

    def __post_init__(self):
        profile = profile_actions.get_profile(self.profile)
        minimum = logical_position_to_motor_turns(self, profile.position_min)
        maximum = logical_position_to_motor_turns(self, profile.position_max)
        motor_actions.set_position_bounds(self.motor, minimum, maximum)
        self.trajectory_velocity_motor_turns = profile_actions.velocity_to_motor_turns(
            profile, profile.trajectory_velocity
        )
        self.trajectory_acceleration_motor_turns = (
            profile_actions.acceleration_to_motor_turns(
                profile, profile.trajectory_acceleration
            )
        )


ctx = create_context("actuator", (Actuator,))


@device_parser(ctx)
def parse_actuator(data: dict) -> Actuator:
    """Parse one logical actuator reference."""
    return Actuator(**data)


def get_names() -> tuple[str, ...]:
    """Return configured actuator component names."""
    return tuple(ctx.store)


@device_action(ctx)
def get_trajectory_velocity_motor_turns(actuator: Actuator) -> float:
    """Return the actuator's configured runtime trajectory speed in motor turns."""
    return actuator.trajectory_velocity_motor_turns


def _profile(actuator: Actuator) -> profile_actions.ActuatorMotionProfile:
    return profile_actions.get_profile(actuator.profile)


def _direction(actuator: Actuator) -> float:
    return -1.0 if _profile(actuator).inverted else 1.0


def logical_position_to_motor_turns(
    actuator: Actuator, quantity: profile_actions.MotionQuantity
) -> float:
    """Convert logical position to signed raw motor turns."""
    profile = _profile(actuator)
    if profile.ballscrew_linkage is not None:
        angle = profile_actions.position_to_degrees(profile, quantity)
        displacement = profile_actions.actuator_x(angle, profile.ballscrew_linkage)
        pitch = profile_actions.ballscrew_pitch_centimeters(profile.ballscrew_linkage)
        offset = profile_actions.length_centimeters(
            profile.ballscrew_linkage.x_offset, "x_offset"
        )
        return (displacement - offset) / pitch * _direction(actuator)
    if profile.motor_turns_per_actuator_turn is None:
        raise ValueError("linear actuator profile requires a motor ratio")
    actuator_turns = profile_actions.position_to_actuator_turns(profile, quantity)
    return actuator_turns * profile.motor_turns_per_actuator_turn * _direction(actuator)


@device_action(ctx)
def position_to_motor_turns(actuator: Actuator, value: float, unit="degrees") -> float:
    """Convert a logical position to signed raw motor turns."""
    return logical_position_to_motor_turns(
        actuator, profile_actions.MotionQuantity(value, unit)
    )


@device_action(ctx)
def motor_turns_to_position(actuator: Actuator, turns: float, unit="degrees") -> float:
    """Convert signed raw motor turns to a logical position."""
    profile = _profile(actuator)
    if profile.ballscrew_linkage is not None:
        pitch = profile_actions.ballscrew_pitch_centimeters(profile.ballscrew_linkage)
        offset = profile_actions.length_centimeters(
            profile.ballscrew_linkage.x_offset, "x_offset"
        )
        angle = profile_actions.knee_angle(
            turns * _direction(actuator) * pitch + offset,
            profile.ballscrew_linkage,
        )
        if unit == "degrees":
            return angle
        if unit == "actuator_turns":
            return angle / 360.0
        raise ValueError(f'unsupported nonlinear position unit "{unit}"')
    ratio = profile.motor_turns_per_actuator_turn
    if ratio is None:
        raise ValueError("linear actuator profile requires a motor ratio")
    actuator_turns = turns * _direction(actuator) / ratio
    if unit == "degrees":
        return actuator_turns * 360.0
    if unit == "actuator_turns":
        return actuator_turns
    if unit == "motor_turns":
        return actuator_turns * ratio
    raise ValueError(f'unsupported position unit "{unit}"')


@device_action(ctx)
def velocity_to_motor_turns(
    actuator: Actuator,
    value: float,
    unit="degrees_per_second",
    position_motor_turns: float | None = None,
) -> float:
    """Convert a logical signed velocity to raw motor turns per second."""
    profile = _profile(actuator)
    if profile.ballscrew_linkage is not None and unit == "degrees_per_second":
        if position_motor_turns is None:
            raise ValueError("nonlinear velocity conversion requires motor position")
        angle = motor_turns_to_position(actuator, position_motor_turns)
        turns_per_degree = _nonlinear_motor_turns_per_degree(actuator, angle)
        return value * turns_per_degree
    magnitude = profile_actions.velocity_to_motor_turns(
        profile, profile_actions.MotionQuantity(value, unit)
    )
    return magnitude * _direction(actuator)


@device_action(ctx)
def motor_turns_to_velocity(
    actuator: Actuator,
    turns: float,
    unit="degrees_per_second",
    position_motor_turns: float | None = None,
) -> float:
    """Convert raw signed motor velocity to logical velocity."""
    profile = _profile(actuator)
    if profile.ballscrew_linkage is not None:
        if unit != "degrees_per_second":
            raise ValueError(f'unsupported nonlinear velocity unit "{unit}"')
        if position_motor_turns is None:
            raise ValueError("nonlinear velocity conversion requires motor position")
        angle = motor_turns_to_position(actuator, position_motor_turns)
        turns_per_degree = _nonlinear_motor_turns_per_degree(actuator, angle)
        if abs(turns_per_degree) <= 1e-12:
            raise ValueError("nonlinear linkage is singular at this position")
        return turns / turns_per_degree
    ratio = profile.motor_turns_per_actuator_turn
    if ratio is None:
        raise ValueError("linear actuator profile requires a motor ratio")
    actuator_turns = turns * _direction(actuator) / ratio
    if unit == "degrees_per_second":
        return actuator_turns * 360.0
    if unit == "actuator_turns_per_second":
        return actuator_turns
    if unit == "motor_turns_per_second":
        return actuator_turns * ratio
    raise ValueError(f'unsupported velocity unit "{unit}"')


@device_action(ctx)
def validate_target_position(actuator: Actuator, value: float, unit="degrees") -> float:
    """Validate a logical target and return its signed raw motor position."""
    if not math.isfinite(value):
        raise ValueError("target position must be finite")
    profile = _profile(actuator)
    logical_degrees = profile_actions.position_to_degrees(
        profile, profile_actions.MotionQuantity(value, unit)
    )
    minimum = profile_actions.position_to_degrees(profile, profile.position_min)
    maximum = profile_actions.position_to_degrees(profile, profile.position_max)
    if logical_degrees < minimum or logical_degrees > maximum:
        raise ValueError("target position is outside the actuator profile bounds")
    return position_to_motor_turns(actuator, value, unit)


@device_action(ctx)
def set_target_position(actuator: Actuator, value: float, unit="degrees") -> bool:
    """Validate a logical target against the profile and send it to the motor."""
    return motor_actions.set_target_position(
        actuator.motor, validate_target_position(actuator, value, unit)
    )


@device_action(ctx)
def get_current_position(actuator: Actuator, unit="degrees") -> float | None:
    """Read the latest motor position in logical coordinates."""
    value = motor_actions.get_current_position(actuator.motor)
    return None if value is None else motor_turns_to_position(actuator, value, unit)


@device_action(ctx)
def get_current_velocity(actuator: Actuator, unit="degrees_per_second") -> float | None:
    """Read the latest motor velocity in logical coordinates."""
    value = motor_actions.get_current_velocity(actuator.motor)
    if value is None:
        return None
    position = None
    if _profile(actuator).ballscrew_linkage is not None:
        position = motor_actions.get_current_position(actuator.motor)
        if position is None:
            return None
    return motor_turns_to_velocity(actuator, value, unit, position)


@device_action(ctx)
def set_trajectory_speed(
    actuator: Actuator, value: float, unit="degrees_per_second"
) -> bool:
    """Set this actuator's positive runtime speed without changing its profile."""
    profile = _profile(actuator)
    if profile.ballscrew_linkage is not None and unit == "degrees_per_second":
        position = motor_actions.get_current_position(actuator.motor)
        if position is None:
            raise ValueError("nonlinear speed conversion requires motor position")
        speed = abs(velocity_to_motor_turns(actuator, value, unit, position))
    else:
        speed = profile_actions.velocity_to_motor_turns(
            profile, profile_actions.MotionQuantity(value, unit)
        )
    if speed <= 0:
        raise ValueError("trajectory speed must be a positive magnitude")
    if motor_actions.set_trajectory_velocity(actuator.motor, speed):
        actuator.trajectory_velocity_motor_turns = speed
        return True
    return False


@device_action(ctx)
def set_trajectory_acceleration(actuator: Actuator, value: float) -> bool:
    """Set positive motor turns/s² for both acceleration and deceleration."""
    if not math.isfinite(value) or value <= 0:
        raise ValueError("trajectory acceleration must be finite and positive")
    if motor_actions.set_trajectory_accel(actuator.motor, value):
        actuator.trajectory_acceleration_motor_turns = value
        return True
    return False


@device_action(ctx)
def configure_trajectory(actuator: Actuator) -> bool:
    """Configure position/trapezoidal control and positive trajectory magnitudes."""
    return (
        motor_actions.set_controller_mode(
            actuator.motor, ControlMode.POSITION_CONTROL, InputMode.TRAP_TRAJ
        )
        and motor_actions.set_trajectory_velocity(
            actuator.motor, actuator.trajectory_velocity_motor_turns
        )
        and motor_actions.set_trajectory_accel(
            actuator.motor, actuator.trajectory_acceleration_motor_turns
        )
    )


def _nonlinear_motor_turns_per_degree(actuator: Actuator, angle: float) -> float:
    """Return the signed local ballscrew slope at a logical knee angle."""
    profile = _profile(actuator)
    linkage = profile.ballscrew_linkage
    if linkage is None:
        raise ValueError("nonlinear slope requires a ballscrew linkage")
    radians = math.radians(angle)
    offset = linkage.B - linkage.L1 * math.cos(radians)
    root = math.sqrt(max(linkage.L2**2 - offset**2, 0.0))
    if root <= 1e-12:
        raise ValueError("nonlinear linkage is singular at this position")
    dx_per_radian = -linkage.L1 * math.cos(radians) - (
        offset * linkage.L1 * math.sin(radians) / root
    )
    pitch = profile_actions.ballscrew_pitch_centimeters(linkage)
    return dx_per_radian * math.pi / 180.0 / pitch * _direction(actuator)
