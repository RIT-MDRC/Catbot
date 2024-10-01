import logging
from functools import wraps
from enum import Enum


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
    frequency: int

    def __init__(self, pin: int, initial_value=0.0, frequency=1000):
        self.pin = pin
        self.value = initial_value
        self.frequency = frequency

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

    def write_quick(self, i2c_addr, force=None):
        """
        Perform quick transaction. Throws IOError if unsuccessful.
        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param force:
        :type force: Boolean
        """
        pass

    def read_byte(self, i2c_addr, force=None):
        """
        Read a single byte from a device.

        :rtype: int
        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param force:
        :type force: Boolean
        :return: Read byte value
        """
        pass

    def write_byte(self, i2c_addr, value, force=None):
        """
        Write a single byte to a device.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param value: value to write
        :type value: int
        :param force:
        :type force: Boolean
        """
        pass

    def read_byte_data(self, i2c_addr, register, force=None):
        """
        Read a single byte from a designated register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Register to read
        :type register: int
        :param force:
        :type force: Boolean
        :return: Read byte value
        :rtype: int
        """
        pass

    def write_byte_data(self, i2c_addr, register, value, force=None):
        """
        Write a byte to a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Register to write to
        :type register: int
        :param value: Byte value to transmit
        :type value: int
        :param force:
        :type force: Boolean
        :rtype: None
        """
        pass

    def read_word_data(self, i2c_addr, register, force=None):
        """
        Read a single word (2 bytes) from a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Register to read
        :type register: int
        :param force:
        :type force: Boolean
        :return: 2-byte word
        :rtype: int
        """
        pass

    def write_word_data(self, i2c_addr, register, value, force=None):
        """
        Write a single word (2 bytes) to a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Register to write to
        :type register: int
        :param value: Word value to transmit
        :type value: int
        :param force:
        :type force: Boolean
        :rtype: None
        """
        pass

    def process_call(self, i2c_addr, register, value, force=None):
        """
        Executes a SMBus Process Call, sending a 16-bit value and receiving a 16-bit response

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Register to read/write to
        :type register: int
        :param value: Word value to transmit
        :type value: int
        :param force:
        :type force: Boolean
        :rtype: int
        """
        pass

    def read_block_data(self, i2c_addr, register, force=None):
        """
        Read a block of up to 32-bytes from a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Start register
        :type register: int
        :param force:
        :type force: Boolean
        :return: List of bytes
        :rtype: list
        """
        pass

    def write_block_data(self, i2c_addr, register, data, force=None):
        """
        Write a block of byte data to a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Start register
        :type register: int
        :param data: List of bytes
        :type data: list
        :param force:
        :type force: Boolean
        :rtype: None
        """
        pass

    def block_process_call(self, i2c_addr, register, data, force=None):
        """
        Executes a SMBus Block Process Call, sending a variable-size data
        block and receiving another variable-size response

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Register to read/write to
        :type register: int
        :param data: List of bytes
        :type data: list
        :param force:
        :type force: Boolean
        :return: List of bytes
        :rtype: list
        """
        pass

    def read_i2c_block_data(self, i2c_addr, register, length, force=None):
        """
        Read a block of byte data from a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Start register
        :type register: int
        :param length: Desired block length
        :type length: int
        :param force:
        :type force: Boolean
        :return: List of bytes
        :rtype: list
        """
        print(f"Reading {length} bytes from {i2c_addr} at register {register}")

    def write_i2c_block_data(self, i2c_addr, register, data, force=None):
        """
        Write a block of byte data to a given register.

        :param i2c_addr: i2c address
        :type i2c_addr: int
        :param register: Start register
        :type register: int
        :param data: List of bytes
        :type data: list
        :param force:
        :type force: Boolean
        :rtype: None
        """
        print(f"Writing {data} to {i2c_addr} at register {register}")

    def i2c_rdwr(self, *i2c_msgs):
        """
        Combine a series of i2c read and write operations in a single
        transaction (with repeated start bits but no stop bits in between).

        This method takes i2c_msg instances as input, which must be created
        first with :py:meth:`i2c_msg.read` or :py:meth:`i2c_msg.write`.

        :param i2c_msgs: One or more i2c_msg class instances.
        :type i2c_msgs: i2c_msg
        :rtype: None
        """
        pass


class FakeMCP23017:
    interrupt_enable : int
    interrupt_configuration : int
    io_control : int
    int_flag : list

    def __init__(self):
        pass

    def clear_inta():
        """
        Clears port A interrupts.
        """
        pass

    def clear_intb():
        """
        Clears port B interrupts.
        """
        pass

    def clear_ints():
        """
        Clears interrupts by reading INTCAP.
        """
        pass

    def get_pin(pin):
        """
        Convenience function to create an instance of the DigitalInOut class pointing at the specified pin of this
        MCP23017 device.
        """
        pass


class FakeDirection(Enum):
    INPUT = True
    OUTPUT = False


class FakePull(Enum):
    UP = True
    DOWN = False


