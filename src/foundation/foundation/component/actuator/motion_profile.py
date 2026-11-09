"""Configuration and conversion for logical actuator motion profiles."""

import math
from dataclasses import dataclass, field

from state_management import create_context, device, device_action, device_parser


@dataclass(frozen=True)
class MotionQuantity:
    """A numeric motion value with an explicit unit."""

    value: float
    unit: str

    def __post_init__(self):
        if not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise ValueError("motion quantity value must be finite")


@dataclass(frozen=True)
class BallscrewLinkage:
    """Knee linkage dimensions and ballscrew pitch, expressed in centimeters."""

    L1: float
    L2: float
    A: float
    B: float
    ballscrew_travel_per_motor_turn: MotionQuantity
    x_offset: MotionQuantity = field(
        default_factory=lambda: MotionQuantity(0.0, "centimeters")
    )

    def __post_init__(self):
        dimensions = (self.L1, self.L2, self.A, self.B)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in dimensions
        ):
            raise ValueError("linkage dimensions must be finite numbers")
        if self.L1 <= 0 or self.L2 <= 0 or self.B < 0:
            raise ValueError("invalid linkage dimensions")
        pitch = ballscrew_pitch_centimeters(self)
        if pitch <= 0:
            raise ValueError("ballscrew travel must be a positive magnitude")
        length_centimeters(self.x_offset, "x_offset")


@device
@dataclass(frozen=True)
class ActuatorMotionProfile:
    """Shared actuator conversion, bounds, and trajectory configuration."""

    motor_turns_per_actuator_turn: float | None
    position_min: MotionQuantity
    position_max: MotionQuantity
    trajectory_velocity: MotionQuantity
    trajectory_acceleration: MotionQuantity
    inverted: bool = False
    ballscrew_linkage: BallscrewLinkage | None = None

    def __post_init__(self):
        if type(self.inverted) is not bool:
            raise ValueError("inverted must be a boolean")
        ratio = self.motor_turns_per_actuator_turn
        if self.ballscrew_linkage is None:
            if (
                isinstance(ratio, bool)
                or not isinstance(ratio, (int, float))
                or not math.isfinite(ratio)
                or ratio <= 0
            ):
                raise ValueError(
                    "motor_turns_per_actuator_turn must be finite and positive"
                )
        elif ratio is not None:
            raise ValueError(
                "nonlinear profiles may not define motor_turns_per_actuator_turn"
            )
        minimum = position_to_degrees(self, self.position_min)
        maximum = position_to_degrees(self, self.position_max)
        if minimum >= maximum:
            raise ValueError("position_min must be less than position_max")
        if self.ballscrew_linkage is not None:
            actuator_x(minimum, self.ballscrew_linkage)
            actuator_x(maximum, self.ballscrew_linkage)
        if velocity_to_motor_turns(self, self.trajectory_velocity) <= 0:
            raise ValueError("trajectory_velocity must be a positive magnitude")
        if acceleration_to_motor_turns(self, self.trajectory_acceleration) <= 0:
            raise ValueError("trajectory_acceleration must be a positive magnitude")


ctx = create_context("actuator_motion_profile", (ActuatorMotionProfile,))


@device_action(ctx)
def get_profile(profile: ActuatorMotionProfile) -> ActuatorMotionProfile:
    """Return one immutable configured motion profile."""
    return profile


def _quantity(value, field: str) -> MotionQuantity:
    if not isinstance(value, dict) or set(value) != {"value", "unit"}:
        raise ValueError(f'{field} must contain exactly "value" and "unit"')
    return MotionQuantity(**value)


@device_parser(ctx)
def parse_motion_profile(data: dict) -> ActuatorMotionProfile:
    """Parse and validate one motion profile."""
    data = dict(data)
    for field_name in (
        "position_min",
        "position_max",
        "trajectory_velocity",
        "trajectory_acceleration",
    ):
        data[field_name] = _quantity(data[field_name], field_name)
    linkage = data.get("ballscrew_linkage")
    if linkage is not None:
        linkage = dict(linkage)
        linkage["ballscrew_travel_per_motor_turn"] = _quantity(
            linkage["ballscrew_travel_per_motor_turn"],
            "ballscrew_travel_per_motor_turn",
        )
        if "x_offset" in linkage:
            linkage["x_offset"] = _quantity(linkage["x_offset"], "x_offset")
        data["ballscrew_linkage"] = BallscrewLinkage(**linkage)
        data.setdefault("motor_turns_per_actuator_turn", None)
    return ActuatorMotionProfile(**data)


def ballscrew_pitch_centimeters(linkage: BallscrewLinkage) -> float:
    """Return ballscrew linear travel per motor turn in centimeters."""
    quantity = linkage.ballscrew_travel_per_motor_turn
    if quantity.unit == "millimeters":
        return quantity.value / 10.0
    if quantity.unit == "centimeters":
        return quantity.value
    raise ValueError(f'unsupported ballscrew travel unit "{quantity.unit}"')


def length_centimeters(quantity: MotionQuantity, field_name: str) -> float:
    """Convert a configured length to centimeters."""
    if quantity.unit == "millimeters":
        return quantity.value / 10.0
    if quantity.unit == "centimeters":
        return quantity.value
    raise ValueError(f'unsupported {field_name} unit "{quantity.unit}"')


def actuator_x(angle_degrees: float, linkage: BallscrewLinkage) -> float:
    """Map a knee angle to ballscrew displacement in centimeters."""
    angle = math.radians(angle_degrees)
    radicand = linkage.L2**2 - (linkage.B - linkage.L1 * math.cos(angle)) ** 2
    if radicand < -1e-10:
        raise ValueError("unreachable knee angle")
    return -linkage.L1 * math.sin(angle) - linkage.A + math.sqrt(max(radicand, 0.0))


def knee_angle(displacement: float, linkage: BallscrewLinkage) -> float:
    """Map ballscrew displacement in centimeters to knee angle in degrees."""
    distance = math.hypot(linkage.A + displacement, linkage.B)
    if distance == 0:
        raise ValueError("invalid linkage dimensions")
    cosine = (linkage.L1**2 + distance**2 - linkage.L2**2) / (2 * linkage.L1 * distance)
    if abs(cosine) > 1 + 1e-10:
        raise ValueError("unreachable linkage configuration")
    theta = math.atan2(linkage.B, linkage.A + displacement)
    alpha = math.acos(max(-1.0, min(1.0, cosine)))
    return math.degrees(theta + alpha) - 90.0


def position_to_degrees(
    profile: ActuatorMotionProfile, quantity: MotionQuantity
) -> float:
    """Convert a logical position quantity to degrees."""
    if quantity.unit == "degrees":
        return quantity.value
    if quantity.unit == "actuator_turns":
        return quantity.value * 360.0
    if quantity.unit == "motor_turns":
        if profile.motor_turns_per_actuator_turn is None:
            raise ValueError(
                "motor-turn logical bounds are invalid for nonlinear profiles"
            )
        return quantity.value * 360.0 / profile.motor_turns_per_actuator_turn
    raise ValueError(f'unsupported position unit "{quantity.unit}"')


def position_to_actuator_turns(
    profile: ActuatorMotionProfile, quantity: MotionQuantity
) -> float:
    """Convert a logical position quantity to actuator turns."""
    if profile.motor_turns_per_actuator_turn is None:
        raise ValueError("actuator-turn conversion is invalid for nonlinear profiles")
    return position_to_degrees(profile, quantity) / 360.0


def velocity_to_motor_turns(
    profile: ActuatorMotionProfile, quantity: MotionQuantity
) -> float:
    """Convert a velocity magnitude to motor turns per second."""
    ratio = profile.motor_turns_per_actuator_turn
    if quantity.unit == "degrees_per_second":
        if ratio is None:
            raise ValueError(
                "degree velocity needs a knee position for nonlinear profiles"
            )
        value = quantity.value * ratio / 360.0
    elif quantity.unit == "actuator_turns_per_second":
        if ratio is None:
            raise ValueError(
                "actuator velocity is unsupported for nonlinear profiles"
            )
        value = quantity.value * ratio
    elif quantity.unit == "motor_turns_per_second":
        value = quantity.value
    else:
        raise ValueError(f'unsupported velocity unit "{quantity.unit}"')
    return value


def acceleration_to_motor_turns(
    profile: ActuatorMotionProfile, quantity: MotionQuantity
) -> float:
    """Convert an acceleration magnitude to motor turns per second squared."""
    ratio = profile.motor_turns_per_actuator_turn
    if quantity.unit == "degrees_per_second_squared":
        if ratio is None:
            raise ValueError(
                "degree acceleration is unsupported for nonlinear profiles"
            )
        value = quantity.value * ratio / 360.0
    elif quantity.unit == "actuator_turns_per_second_squared":
        if ratio is None:
            raise ValueError(
                "actuator acceleration is unsupported for nonlinear profiles"
            )
        value = quantity.value * ratio
    elif quantity.unit == "motor_turns_per_second_squared":
        value = quantity.value
    else:
        raise ValueError(f'unsupported acceleration unit "{quantity.unit}"')
    return value
