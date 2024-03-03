import logging
from functools import wraps


def value_change(func: callable) -> callable:
    """
    Decorator for value changed functions.
    Prints the value before and after the function is called for debugging purposes.

    :param func: the function to decorate
    :return: the decorated function

    Debug level message format:
    before: "{function} called: {MockedDevice.pin} {MockedDevice.value}"
    after: "{function} finished: {MockedDevice.pin} {MockedDevice.value}"
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        """
        Decorated function.
        """
        logging.debug(f"{func.__qualname__} called: {args[0].pin} {args[0].value}")
        func(*args, **kwargs)
        logging.debug(f"{func.__qualname__} finished: {args[0].pin} {args[0].value}")

    return wrapper


class FakeDigitalOutputDevice:
    pin: int
    value: int

    def __init__(self, pin: int, initial_value=0):
        self.pin = pin
        self.value = initial_value

    @value_change
    def on(self):
        self.value = 1

    @value_change
    def off(self):
        self.value = 0

    @value_change
    def toggle(self):
        self.value = 1 - self.value

    def __repr__(self) -> str:
        return f"FakeDigitalOutputDevice(pin={self.pin}, value={self.value})"


class FakeDigitalInputDevice:
    pin: int
    value: int
    is_active: bool
    when_activated = None
    when_deactivated = None

    def __init__(self, pin: int, initial_value: int = 0, initial_is_state=False):
        self.pin = pin
        self.value = initial_value
        self.is_active = initial_is_state

    @value_change
    def toggle(self):
        """This is used for debugging purposes only. The state of the device is changed physically in the real world."""
        self.value = 1 - self.value
        self.is_active = self.value == 1
        if self.value == 1 and self.when_activated is not None:
            logging.debug("FakeDigitalInputDevice.toggle: Calling when_deactivated")
            self.when_activated()
            logging.debug("FakeDigitalInputDevice.toggle: Called when_deactivated")
        elif self.value == 0 and self.when_deactivated is not None:
            logging.debug("FakeDigitalInputDevice.toggle: Calling when_deactivated")
            self.when_deactivated()
            logging.debug("FakeDigitalInputDevice.toggle: Called when_deactivated")

    def __repr__(self) -> str:
        return f"FakeDigitalInputDevice(pin={self.pin}, value={self.value}, is_active={self.is_active})"


class FakePWMOutputDevice:
    pin: int
    value: float

    def __init__(self, pin: int, initial_value=0.0):
        self.pin = pin
        self.value = initial_value

    @value_change
    def is_active(self):
        return self.value > 0

    @value_change
    def toggle(self):
        self.value = 1 - self.value

    @value_change
    def on(self):
        self.value = 1

    @value_change
    def off(self):
        self.value = 0

    @value_change
    def toggle(self):
        self.value = 1 - self.value

    @value_change
    def blink(
        self,
        on_time=1,
        off_time=1,
        fade_in_time=0,
        fade_out_time=0,
        n=None,
        background=True,
    ):
        pass

    @value_change
    def pulse(self, fade_in_time=1, fade_out_time=1, n=None, background=True):
        pass

    def __repr__(self) -> str:
        return f"FakePWMOutputDevice(pin={self.pin}, value={self.value})"
