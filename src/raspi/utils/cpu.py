import logging

from gpiozero import CPUTemperature
from utils.util import is_dev, set_interval


def make_cpu() -> CPUTemperature:
    return CPUTemperature()


def setup_cpu(update_func: callable = None):
    if is_dev():
        print("dev environment detected: terminating cpu temp")
        logging.info("dev environment detected: terminating cpu temp")
        return
    cpu = make_cpu()
    set_interval(lambda: update_func(cpu.temperature), 1)
