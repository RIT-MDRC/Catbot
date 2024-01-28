from functools import reduce, wraps
from pydoc import classname

from gpiozero import DigitalInputDevice, DigitalOutputDevice

from ...utils.deviceMock import FakeInputDevice, FakeOutputDevice


def create_device_global_store_definition(component_classes: list):
    """
    Args:
        component_classes (list): This is a list of classes that the device can be. For example, DigitalInputDevice and FakeInputDevice for DigitalInputDevices.

    Returns:
        create_device_component (callable[[str, dict],[callable * 5]]): This is a function that creates a new device component.

    example:
        see src/device.py or src/raspi/io_controller/pneumatics/valve.py
    """

    class_names = "/".join([x.__name__ for x in component_classes])

    def check_class_instance(x):
        return isinstance(x, str) or reduce(
            lambda x, y: x or isinstance(x, y), component_classes, False
        )

    def create_device_component(component_name: str, dict: dict = dict()):
        """
        Create a new output device component.

        returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
        """

        def register_device(name: str, device) -> None:
            """
            Add a new device to the list of devices.

            Args:
                name (str): the name/identifier of the device
                device (): the device number of the device
            """
            if name in dict:
                raise ValueError(f"{component_name} {name} already exists")
            elif not check_class_instance(device):
                raise ValueError(f"Must be a identifier(string) or " + class_names)
            dict[name] = device

        def get_device(name: str):
            """
            Get the device number of a device.

            Args:
                name (str): the name of the device

            Returns:
                (int) the device number of the device
            """
            return dict[name]

        def get_registered_devices():
            """
            Get a list of all the device pins.

            Returns:
                (list[int]) a list of all the device pins
            """
            return list(dict.values())

        def get_registered_device_names():
            """
            Get a list of all the device names.

            Returns:
                (list[str]) a list of all the device names
            """
            return list(dict.keys())

        def device_action(func: callable) -> callable:
            """
            Decorator for device actions.

            Args:
                func (callable): the function to decorate

            Returns:
                (callable) the decorated function
            """

            @wraps(func)
            def wrapper(*args, **kwargs):
                if len(args) < 1:
                    raise ValueError("Missing argument")
                if not check_class_instance(args[0]):
                    raise ValueError(
                        "First argument must be a identifier(string) or " + class_names
                    )
                valve = get_device(args[0]) if isinstance(args[0], str) else args[0]
                if valve is None:
                    raise ValueError(f"{component_name} {args[0]} does not exist")
                return func(valve, *args[1:], **kwargs)

            return wrapper

        return (
            device_action,
            register_device,
            get_device,
            get_registered_devices,
            get_registered_device_names,
            dict,
        )

    return create_device_component


create_input_device_component = create_device_global_store_definition(
    [DigitalInputDevice, FakeInputDevice]
)
"""
Create a new input device component.
returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
"""


create_output_device_component = create_device_global_store_definition(
    [DigitalOutputDevice, FakeOutputDevice]
)
"""
Create a new output device component.
returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
"""
