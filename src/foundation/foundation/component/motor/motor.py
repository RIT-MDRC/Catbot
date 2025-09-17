from dataclasses import dataclass

from state_management import (
    create_context,
    device,
    device_action,
    device_parser,
    identifier,
)

from . import raw_motor_actions


@device
@dataclass
class Motor:
    raw_motor = identifier(raw_motor_actions.ctx)
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
    raw_motor_actions.step_n(motor.raw_motor, n)
