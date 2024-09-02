from dataclasses import dataclass
import logging

from state_management import (
    device,
    input_device_ctx,
    identifier,
    create_context,
    device_parser,
    device_action,
)
from . import raw_motor_action

# from component.limit_switch import limit_switch_actions


@device
@dataclass
class Motor:
    raw_motor = identifier(raw_motor_action.ctx)
    # negative_limit_switch = identifier(input_device_ctx)
    # positive_limit_switch = identifier(input_device_ctx)


ctx = create_context("motor", (Motor,))


@device_parser(ctx)
def parse_motor(config):
    motor = Motor(**config)

    # limit_switch_actions.on_limit_switch_activated(
    #     motor.positive_limit_switch,
    #     lambda: raw_motor_action.step_n(motor.raw_motor, -1),
    # )
    # limit_switch_actions.on_limit_switch_activated(
    #     motor.negative_limit_switch, lambda: raw_motor_action.step_n(motor.raw_motor, 1)
    # )
    return motor


@device_action(ctx)
def step_n(motor: Motor, n: int):
    raw_motor_action.step_n(motor.raw_motor, n)
