from functools import wraps
from typing import Any
from gpiozero import DigitalInputDevice, DigitalOutputDevice


def value_change(func: callable) -> callable:
    """
    Decorator for value changed functions.
    Prints the value before and after the function is called for debugging purposes.

    :param func: the function to decorate
    :return: the decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        """
        Decorated function.
        """
        print(f"Value changed: {args[0].pin} {args[0].value}", end=" -> ")
        func(*args, **kwargs)
        print(f"{args[0].value}")

    return wrapper


class FakeOutputDevice:
    def __init__(self, pin: int):
        self.pin = pin
        self.value = 0

    @value_change
    def on(self):
        self.value = 1

    @value_change
    def off(self):
        self.value = 0

    @value_change
    def toggle(self):
        self.value = 1 - self.value


class FakeInputDevice:
    when_activated = None
    when_deactivated = None

    def __init__(self, pin: int):
        self.pin = pin
        self.value = 0
        self.is_active = False

    def toggle(self):
        """This is used for debugging purposes only. The state of the device is changed physically in the real world."""
        self.value = 1 - self.value
        self.is_active = self.value == 1
        if self.value == 1 and self.when_activated is not None:
            print("(Dev) calling when_activated")
            self.when_activated()
        elif self.value == 0 and self.when_deactivated is not None:
            print("(Dev) calling when_deactivated")
            self.when_deactivated()


class FakePWMOutputDevice:
    pin: int
    value: float

    def __init__(self, pin: int):
        self.pin = pin
        self.value = 0

    @value_change
    def is_active(self):
        return self.value > 0

    @value_change
    def toggle(self):
        self.value = 1 - self.value
