import json
from collections import namedtuple
from functools import reduce, wraps

Parser = namedtuple("Parser", ["register_device", "parse_device", "store"])
DEVICE_PARSERS: dict[str, Parser] = dict()


def create_generic_device_store(
    generic_component_name: str, component_classes: list, parser_func: callable = None
):
    """
    Create a generic device store.
    Use this to create a device that is usually renamed to a different component. Components that are just Pins are good examples.
    For example:
    - InputDevice
    - OutputDevice
    - PWMOutputDevice
    - DigitalInputDevice

    Use the returned method from this method to rename the component.
    For example:
    - valve from generic digital output device
    - handshake from generic digital input device
    - speedPin from generic pwm output device

    This allows us to create a single store for all generic devices during parsing.

    Do not use this to create a specific device.
    For example:
    - MotorController
    - MuscleController

    Those should be created using create_component_store.

    Args:
        component_classes (list): This is a list of classes that the device can be. For example, DigitalInputDevice and FakeInputDevice for DigitalInputDevices used for type checking.

    Returns:
        create_device_component (callable[[str], callable]]): This is a function that creates a new device component that is just a reskin of the generic device.

    example:
        see src/device.py or src/raspi/io_controller/pneumatics/valve.py
    """

    class_names = "/".join([x.__name__ for x in component_classes])

    generic_store: dict = dict()

    if parser_func is not None:
        device_parser(parser_func)

    def check_class_instance(x):
        return isinstance(x, str) or reduce(
            lambda res, y: res or isinstance(x, y), component_classes, False
        )

    def generic_register_device(name: str, device=None) -> None:
        """
        Add a new device to the list of devices.

        Args:
            name (str): the name/identifier of the device
            device (): the device number of the device
        """
        if name in generic_store:
            raise ValueError(f"{generic_component_name} {name} already exists")
        elif not check_class_instance(device):
            raise ValueError(f"Must be a identifier(string) or " + class_names)
        elif not device is None:
            generic_store[name] = device

    def device_parser(func: callable):
        """
        Decorator for device parsers.

        Args:
            func (callable): the function to decorate

        Returns:
            (callable) the decorated function
        """
        DEVICE_PARSERS[generic_component_name] = Parser(
            generic_register_device, func, generic_store
        )

    def create_device_component(component_name: str):
        """
        Create a new output device component.

        Args:
            component_name (str): the name of the component (used in error messages)
            dict (dict): the dictionary to store the devices in
        returns: tuple[device_action, device_parser]
        """

        UNIQUE_COMPONENT_IDENTIFIERS = set()

        DEVICE_PARSERS[component_name] = Parser(
            local_register_device,
            DEVICE_PARSERS[generic_component_name].parse_device,
            DEVICE_PARSERS[generic_component_name].store,
        )

        def local_component_identifier(name: str) -> str:
            """This is used to create a unique identifier for the component. This is used to store the device in the global store.
            UNIQUE_COMPONENT_IDENTIFIERS does not use this and has the regualar name. This is used to store the device in the global store.
            """
            return component_name + "_" + name

        def local_register_device(name: str, device) -> None:
            """
            Add a new device to the list of devices.

            Args:
                name (str): the name/identifier of the device
                device (): the device number of the device
            """
            if name in UNIQUE_COMPONENT_IDENTIFIERS:
                raise ValueError(f"{component_name} {name} already exists")
            elif (
                not local_component_identifier(name) in generic_store and device is None
            ):
                raise ValueError(f"{component_name} {name} does not exist")
            elif not check_class_instance(device):
                raise ValueError(f"Must be a identifier(string) or " + class_names)
            elif not device is None:
                generic_store[local_component_identifier(name)] = device
            UNIQUE_COMPONENT_IDENTIFIERS.add(name)

        def get_device(name: str):
            """
            Get the device number of a device.

            Args:
                name (str): the name of the device

            Returns:
                (int) the device number of the device
            """
            if not name in UNIQUE_COMPONENT_IDENTIFIERS:
                raise ValueError(f"{component_name} {name} does not exist")
            return generic_store.get(local_component_identifier(name))

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

        return device_action

    return create_device_component, device_parser


def open_json(file_name: str = "pinconfig.json"):
    with open(file_name, "r") as file:
        config = json.load(file)
    for key, value in config.items():
        yield key, value


def configure_device(file_name: str = "pinconfig.json", file_kv_generator=open_json):
    """configure the devices from the pinconfig file. This will parse the devices and store them in the global store.

    Args:
        file_name (str, optional): file of the pinconfiguration. Defaults to "pinconfig.json".
        file_kv_generator (callable[[file_name: str], Generator[tuple[str, Any], Any, None]], optional): function for opening the pinconfig. Defaults to open_json.
    """
    for key, config in file_kv_generator(file_name):
        if not key in DEVICE_PARSERS:
            continue
        parser = DEVICE_PARSERS[key]
        device = parser.parse_device(config)
        parser.register_device(key, device)


def create_component_store(
    component_name: str, component_classes: list, parser_func=None
):
    """_summary_

    Args:
        component_name (str): name of the component (used in error messages)
        component_classes (list): classes that the device can be. For example, `[DigitalInputDevice, FakeInputDevice]` for DigitalInputDevice Store. (used to check if the device is a valid device)
        parser_func (callable, optional): function to parse the device. Defaults to None.

    Returns:
        device_action (callable): decorator for device actions,
    """
    create_device, device_parser = create_generic_device_store(
        component_name, component_classes, parser_func
    )
    device_action = create_device(component_name)
    return device_action, device_parser
