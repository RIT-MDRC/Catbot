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


class FakeSMBus:
    def __init__(self, bus: int):
        self.bus = bus

    def read_byte_data(self, i2c_addr: int, register: int) -> int:
        logging.info(
            f"FakeSMBus.read_byte_data: Reading from address:{i2c_addr} at register:{register}"
        )
        return 0

    def write_byte_data(self, i2c_addr: int, register: int, value: int) -> None:
        logging.info(
            f"FakeSMBus.write_byte_data: Writing value:{value} to address:{i2c_addr} at register:{register}"
        )
        pass

    def read_word_data(self, i2c_addr: int, register: int) -> int:
        logging.info(
            f"FakeSMBus.read_word_data: Reading from address:{i2c_addr} at register:{register}"
        )
        return 0

    def write_word_data(self, i2c_addr: int, register: int, value: int) -> None:
        logging.info(
            f"FakeSMBus.write_word_data: Writing value:{value} to address:{i2c_addr} at register:{register}"
        )
        pass

    def read_i2c_block_data(self, i2c_addr: int, register: int, length: int) -> list:
        logging.info(
            f"FakeSMBus.read_i2c_block_data: Reading from address:{i2c_addr} at register:{register} with length:{length}"
        )
        return [0] * length

    def write_i2c_block_data(self, i2c_addr: int, register: int, data: list) -> None:
        logging.info(
            f"FakeSMBus.write_i2c_block_data: Writing data:{data} to address:{i2c_addr} at register:{register}"
        )
        pass

    def close(self) -> None:
        logging.info("FakeSMBus.close: Closing the bus")
        pass

    def __repr__(self) -> str:
        return f"FakeSMBus(bus={self.bus})"
