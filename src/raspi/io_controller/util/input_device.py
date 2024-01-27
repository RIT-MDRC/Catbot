from functools import wraps

from gpiozero import DigitalInputDevice

from ...utils.deviceMock import FakeInputDevice


def create_input_device_component(component_name: str, dict: dict = dict()):
    """
    Create a new output device component.

    returns: (device_action, register_device, get_device, get_registered_devices, get_registered_device_names, gloabal_store)
    """

    def register_device(name: str, device) -> None:
        """
        Add a new device to the list of devices.

        Args:
            name (str): the name/identifier of the device
            device (int): the device number of the device
        """
        if name in dict:
            raise ValueError(f"{component_name} {name} already exists")
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
            elif not (
                isinstance(args[0], str)
                or isinstance(args[0], DigitalInputDevice)
                or isinstance(args[0], FakeInputDevice)
            ):
                raise ValueError(
                    "First argument must be a string/identifier or a DigitalInputDevice"
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
