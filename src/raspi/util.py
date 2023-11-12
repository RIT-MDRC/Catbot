from gpiozero import InputDevice, OutputDevice


def create_input_device(pin: int) -> InputDevice:
    """
    Create a new input device.

    :param pin: the pin number of the device
    :return: the device object
    """
    return InputDevice(pin)


create_pressure_device = create_input_device
"""Create a new pressure device (alias for create_input_device)"""


def create_output_device(pin: int) -> OutputDevice:
    """
    Create a new output device.

    :param pin: the pin number of the device
    :return: the device class
    """
    return OutputDevice(pin)


create_valve_device = create_output_device
"""Create a new valve device (alias for create_output_device)"""


def create_dataclass(dataclass: object, data: dict) -> object:
    for key in data.keys():
        k = key.split("_")[-1]
        dataclass[k] = key
    return dataclass
