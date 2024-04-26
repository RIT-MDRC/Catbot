import logging
import threading

intervals = []
timeouts = []


def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()

    t = threading.Timer(sec, func_wrapper)
    t.start()
    intervals.append(t)
    return t


def clear_intervals():
    for interval in intervals:
        interval.cancel()
    intervals.clear()


def set_timeout(func, sec):
    t = threading.Timer(sec, func)
    t.start()
    timeouts.append(t)
    return len(timeouts) - 1


def clear_timeouts():
    for timeout in timeouts:
        timeout.cancel()
    timeouts.clear()


def clear_all():
    clear_intervals()
    clear_timeouts()


def debounce(func, sec):
    """Create a debounced function.
    Will only call the function after the time has passed since the last call.

    Args:
        func (callable): functions to debounce
        sec (int): time in seconds to debounce

    example:
    ```python
    def print_hello():
        print("hello")

    debounced_print_hello = debounce(print_hello, 1)
    debounced_print_hello()
    debounced_print_hello()
    debounced_print_hello()
    debounced_print_hello()
    ```
    """

    def func_wrapper():
        if hasattr(func_wrapper, "timer"):
            func_wrapper.timer.cancel()
        func_wrapper.timer = threading.Timer(sec, func)
        func_wrapper.timer.start()

    return func_wrapper
