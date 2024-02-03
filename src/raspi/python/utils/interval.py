import threading

intervals = []


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
