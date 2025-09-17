#!/usr/bin/env /workspace/.venv/bin/python

import logging
import os
from dataclasses import dataclass, field
from typing import Union

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.node import Node
from std_msgs.msg import Empty, Float64

from component.adc import adc_actions
from component.compressor import compressor_actions
from component.motor import motor_actions, motor_enums
from component.muscle import muscle_actions, pressure_actions
from state_management import configure_device
from state_management._device import Context

adc_actions.USE = True

COMPRESSOR = "main_compressor"
COMPRESSOR_THRESHOLD = 600
MOTORS = ["odrive_1", "odrive_2"]


@dataclass
class DeviceActionSubscriber:
    topic: str
    callback: callable
    context: Context = field(default=None)
    paramType: object = field(default=Empty)

    def __post_init__(self):
        if self.context is None and hasattr(self.callback, "_ctx"):
            self.context = self.callback._ctx
        self.topic = self.callback._func_path if self.topic is None else self.topic

        assert callable(self.callback), "Callback must be a callable"
        assert self.context is not None, "Callback must have a context"
        assert self.topic is not None, "Topic must be provided"


@dataclass
class DeviceActionTimer:
    period: float
    callback: Union[callable, list[callable]]

    def __post_init__(self):
        if not isinstance(self.callback, list):
            self.callback = [self.callback]


# Subscribers
SUBSCRIBER_DEVICE_ACTION_CALLBACKS = [
    {
        "topic": "motor/set_target_position",
        "callback": lambda device, data: motor_actions.set_target_velocity(
            device, data.data
        ),
        "context": motor_actions.ctx,
        "paramType": Float64,
    },
    {
        "topic": "muscle/contract",
        "callback": lambda device, _: muscle_actions.contract(device),
        "context": muscle_actions.ctx,
    },
    {
        "topic": "muscle/relax",
        "callback": lambda device, _: muscle_actions.relax(device),
        "context": muscle_actions.ctx,
    },
]

check_count = 100
enabled = False


def check_pressure(presure_device, compressor_device=None):
    global enabled, check_count
    value = pressure_actions.get_pressure(presure_device)
    reading = f"Reading {presure_device} {check_count}: {value}"
    print(reading)
    logging.info(reading)
    if not compressor_device is None:
        if not enabled:
            enabled = True
            compressor_actions.turn_compressor_on(compressor_device)
            return
        if value < COMPRESSOR_THRESHOLD:
            check_count -= 1
            return
        elif value > COMPRESSOR_THRESHOLD or check_count <= 0:
            compressor_actions.turn_compressor_off(compressor_device)


TIMER_DEVICE_ACTION_CALLBACKS = [
    # {
    #     "period": 0.2,
    #     "callback": [
    #         lambda: check_pressure("adc_1.pot1"),
    #         lambda: check_pressure("adc_1.pot2"),
    #         lambda: check_pressure("adc_1.pot3"),
    #         lambda: check_pressure("adc_1.pot4"),
    #         lambda: check_pressure("adc_1.pot5"),
    #         lambda: check_pressure("adc_1.pot6"),
    #         lambda: check_pressure("adc_1.pot7"),
    #         lambda: check_pressure("adc_1.pot8"),
    #     ],
    # }
]


class DeviceActionSubscriberNode(Node):
    callback_group: MutuallyExclusiveCallbackGroup
    subs: list[dict]
    ti: list[dict]

    def __init__(self, nodeName, subscribers, timers):
        configure_device(os.path.join(f"{os.path.dirname(__file__)}/pinconfig.json"))
        super().__init__(nodeName)
        self.subs = subscribers
        self.ti = timers
        self.callback_group = MutuallyExclusiveCallbackGroup()
        # for motor in MOTORS:
        #     motor_actions.clear_error_message(motor)

    def setup_timers(self):
        timers_info = [DeviceActionTimer(**timer) for timer in self.ti]
        for timer in timers_info:

            def timer_callback():
                for callback in timer.callback:
                    callback()

            self.create_timer(
                timer.period, timer_callback, callback_group=self.callback_group
            )

    def setup_subscribers(self):
        # Create a Mutex CallbackGroup
        subscribers_info = [
            DeviceActionSubscriber(**subscriber) for subscriber in self.subs
        ]
        # Iterate through the list of tuples and create subscribers
        for subscriber in subscribers_info:
            topic = subscriber.topic
            callback = subscriber.callback
            context = subscriber.context
            paramType = subscriber.paramType
            for device_name, device in context.store.items():
                path = f"{topic}/{device_name}"

                def dev_callback(msg, callback=callback, path=path, device=device):
                    logging.info(f"Received message on {path}: {msg}")
                    print(f"Received message on {path}: {msg}")
                    try:
                        callback(
                            device, msg
                        )  # closure issue may arise if context store is changed
                    except Exception as e:
                        logging.error(f"Error: {e}")
                        self.get_logger().error(f"Error: {e}")

                self.create_subscription(
                    Empty if paramType is None else paramType,
                    path,  # Topic path
                    dev_callback,  # Callback function
                    10,  # QoS profile depth
                    callback_group=self.callback_group,  # Use the Mutex callback group
                )


def main(args=None):
    rclpy.init(args=args)

    node = DeviceActionSubscriberNode(
        "foundation_node",
        SUBSCRIBER_DEVICE_ACTION_CALLBACKS,
        TIMER_DEVICE_ACTION_CALLBACKS,
    )
    node.setup_subscribers()
    node.setup_timers()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    rclpy.shutdown()


if __name__ == "__main__":
    main()
