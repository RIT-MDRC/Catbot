import json
import logging
from collections import namedtuple
from functools import reduce, wraps

Parser = namedtuple("Parser", ["register_device", "parse_device", "store"])
DEVICE_PARSERS: dict[str, Parser] = dict()


def create_generic_device_store(
    generic_device_name: str, device_classes: list, parser_func: callable = None
):
    """
    # Create Generic Device Store
    Initializes a generic device store.

    Args:
        component_classes (list): This is a list of classes that the device can be. For example, DigitalInputDevice and FakeInputDevice for DigitalInputDevices used for type checking.

    Returns:
        create_masked_device (callable[[str], callable]]): This is a function that creates a new device component that is just a reskin of the generic device.
        *device_parser (callable): This is a function that parses the device from the config.

    *device_parser should not be exportable outside of the file. This will overwrite the parser function for the generic device store and create unexpected behavior when parsed multiple times.

    example:
        see src/device.py or src/raspi/io_controller/pneumatics/valve.py
    """

    class_names = "/".join([x.__name__ for x in device_classes])

    generic_store: dict = dict()

    if parser_func is not None:
        device_parser(parser_func)

    def check_class_instance(x):
        return isinstance(x, str) or reduce(
            lambda res, y: res or isinstance(x, y), device_classes, False
        )

    def generic_register_device(name: str, device) -> None:
        """
        Add a new device to the list of devices.

        Args:
            name (str): the name/identifier of the device
            device (): the device number of the device
        """
        if name in generic_store:
            raise ValueError(f"{generic_device_name} {name} already exists")
        elif not check_class_instance(device):
            raise ValueError(f"Must be a identifier(string) or " + class_names)
        elif not device is None:
            generic_store[name] = device

    def device_parser(func: callable):
        """
        # Device Parser
        Decorator for device parsers.

        Args:
            func (callable[[int],None]): the function to decorate

        Returns:
            None
        """
        DEVICE_PARSERS[generic_device_name] = Parser(
            generic_register_device, func, generic_store
        )

    def create_masked_device(device_name: str):
        """
        # Create Masked Device
        Create a new device component from a generic device store.

        Args:
            device_name (str): the name of the component (used in error messages)
            dict (dict): the dictionary to store the devices' state

        Returns:
            device_action: `callable[[str],(func: Any) -> Any]`
        """

        UNIQUE_COMPONENT_IDENTIFIERS = set()

        DEVICE_PARSERS[device_name] = Parser(
            local_register_device,
            DEVICE_PARSERS[generic_device_name].parse_device,
            DEVICE_PARSERS[generic_device_name].store,
        )

        def local_component_identifier(name: str) -> str:
            """This is used to create a unique identifier for the component. This is used to store the device in the global store.
            UNIQUE_COMPONENT_IDENTIFIERS does not use this and has the regualar name. This is used to store the device in the global store.
            """
            return device_name + "_" + name

        def local_register_device(name: str, device) -> None:
            """
            Add a new device to the list of devices.

            Args:
                name (str): the name/identifier of the device
                device (): the device number of the device
            """
            if name in UNIQUE_COMPONENT_IDENTIFIERS:
                raise ValueError(f"{device_name} {name} already exists")
            elif (
                not local_component_identifier(name) in generic_store and device is None
            ):
                raise ValueError(f"{device_name} {name} does not exist")
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
                raise ValueError(f"{device_name} {name} does not exist")
            return generic_store.get(local_component_identifier(name))

        def device_action(func: callable) -> callable:
            """
            # Device Action
            Decorator for device actions. Requirements for the decorated function below.

            Args:
                func (callable): the action function to decorate

            Returns:
                (callable) the decorated function

            ## Requirements for the decorated function:
            - The first argument must be the device state
            - The rest of the arguments are for extra arguments for the function to work
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
                    raise ValueError(f"{device_name} {args[0]} does not exist")
                return func(valve, *args[1:], **kwargs)

            return wrapper

        return device_action

    return create_masked_device, device_parser


def open_json(file_name: str = "pinconfig.json"):
    with open(file_name, "r") as file:
        config = json.load(file)
    for key, value in config.items():
        yield key, value


def configure_device(
    file_name: str = "pinconfig.json", file_kv_generator: callable = open_json
):
    """configure the devices from the pinconfig file. This will parse the devices and store them in the global store.

    Args:
        file_name (str, optional): file of the pinconfiguration. Defaults to "pinconfig.json".
        file_kv_generator (callable[[file_name: str], Generator[tuple[str, Any], Any, None]], optional): function for opening the pinconfig. Defaults to open_json.

    Details:
        file_kv_generator is a function that takes in a file name and returns a generator that yields a tuple of the key and the value. This is used to open the pinconfig file and parse the devices.
        The expected behavior is that the file_kv_generator will parse the config and return a generator for the first layer of key and value pairs. The key should be the identifier of the device parser and the value should be the object with device identifier and attributes.

    WARNING:
        This method will skip any parser that was not registered in the device parser list.
        This could happen for two reasons. The device store was not initialized due to the file that the initializer is in was not imported in the script file(memory benefit), or the parser's identifier had a typo in the pinconfig file(Will need to be fixed immediately).
    """
    for key, config in file_kv_generator(file_name):
        if not key in DEVICE_PARSERS:
            logging.warning(
                f"{key} does not registered in the device parser list. Skipping..."
            )
            continue
        parser = DEVICE_PARSERS[key]
        for key, device_attr in config.items():
            device = parser.parse_device(device_attr)
            parser.register_device(key, device)


def create_device_store(
    component_name: str, component_classes: list, parser_func: callable = None
):
    """
    # Create Device Store
    This is the main method for creating a store for any device. This method under the hood calls the `create_generic_device_store` method and returns the `create_device` method and `device_parser` method. Use this to create non-generic devices.

    Args:
        component_name (str): name of the component (used in error messages)
        component_classes (list): classes that the device can be. For example, `[DigitalInputDevice, FakeInputDevice]` for DigitalInputDevice Store. (used to check if the device is a valid device)
        parser_func (callable, optional): function to parse the device. Defaults to None.

    Returns:
        device_action (callable): decorator for device actions,
        device_parser (callable): function to parse the device from config
    """
    create_device, device_parser = create_generic_device_store(
        component_name, component_classes, parser_func
    )
    device_action = create_device(component_name)
    return device_action, device_parser
