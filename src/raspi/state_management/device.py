import inspect
import json
import logging
from collections import namedtuple
from functools import reduce, wraps
from typing import Union

Parser = namedtuple(
    "Parser",
    [
        "register_device",  # callable[[str, any], None]:   the function to register a new device
        "parse_device",  # callable[[dict, str], any]:      the function to parse a new device from the config file
        "store",  # dict:                                   the dictionary to store the devices
        "masked_device_parsers",  # list:                   the list of masked device parsers
        "stored_keys",  # set:                              the set of keys that are stored in the store for masked devices
    ],
)
"""Parser Class

    Attributes:
        register_device (callable[[str, any], None]):   function to register a new device
        parse_device (callable[[dict, str], any]):      function to parse a new device
        store (dict):                                   dictionary to store the devices' state
        masked_device_parsers (list):                   list of sub parsers
        stored_keys (set):                              set of keys that are stored in the store for masked devices
"""
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

    def check_only_class_instance(x):
        return reduce(lambda res, y: res or isinstance(x, y), device_classes, False)

    def check_class_instance(x):
        return isinstance(x, str) or reduce(
            lambda res, y: res or isinstance(x, y), device_classes, False
        )

    def register_generic_device(name: str, device) -> None:
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

    def device_parser(func: callable = None):
        """
        # Device Parser
        Decorator for device parsers.

        Args:
            func (callable[[int],None]): the function to decorate

        Returns:
            None
        """

        def wrapped_func(value, _identifier):
            if isinstance(value, dict):
                value["_identifier"] = _identifier
            device = func(value)
            return device

        # Update parser_device
        if generic_device_name in DEVICE_PARSERS:
            parser = DEVICE_PARSERS[generic_device_name]
            DEVICE_PARSERS[generic_device_name] = Parser(
                register_device=parser.register_device,
                parse_device=wrapped_func,
                store=generic_store,
                masked_device_parsers=parser.masked_device_parsers,
                stored_keys=parser.stored_keys,
            )
            for sub_parser in parser.masked_device_parsers:
                parser = DEVICE_PARSERS[sub_parser]
                DEVICE_PARSERS[sub_parser] = Parser(
                    register_device=parser.register_device,
                    parse_device=wrapped_func,
                    store=parser.store,
                    masked_device_parsers=parser.masked_device_parsers,
                    stored_keys=parser.stored_keys,
                )
            return

        parser = Parser(
            register_generic_device, wrapped_func, generic_store, list(), None
        )
        DEVICE_PARSERS[generic_device_name] = parser

    device_parser(parser_func)

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

        def local_register_device(name: str, device) -> None:
            """
            Add a new device to the list of devices.

            Args:
                name (str): the name/identifier of the device
                device (): the device number of the device
            """
            if name in UNIQUE_COMPONENT_IDENTIFIERS:
                raise ValueError(f"{device_name} {name} already exists")
            elif not name in generic_store and device is None:
                raise ValueError(
                    f"{device_name}: {name} does not exist in generic store and device is None"
                )
            elif not check_class_instance(device):
                raise ValueError(f"Must be a identifier(string) or " + class_names)
            elif name not in generic_store:
                generic_store[name] = device
            UNIQUE_COMPONENT_IDENTIFIERS.add(name)

        # Create parser for the masked device
        DEVICE_PARSERS[device_name] = Parser(
            register_device=local_register_device,
            parse_device=DEVICE_PARSERS[generic_device_name].parse_device,
            store=DEVICE_PARSERS[generic_device_name].store,
            masked_device_parsers=list(),
            stored_keys=UNIQUE_COMPONENT_IDENTIFIERS,
        )
        DEVICE_PARSERS[generic_device_name].masked_device_parsers.append(device_name)

        def get_device(name: str):
            """
            Get the device number of a device.

            Args:
                name (str): the name of the device

            Returns:
                (int) the device number of the device
            """
            if not name in UNIQUE_COMPONENT_IDENTIFIERS:
                raise ValueError(f"{device_name}: {name} does not exist")
            return generic_store.get(name)

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
                value = get_device(args[0]) if isinstance(args[0], str) else args[0]
                if value is None:
                    raise ValueError(
                        f"{UNIQUE_COMPONENT_IDENTIFIERS} {device_name} {args[0]} does not exist"
                    )
                return func(value, *args[1:], **kwargs)

            return wrapper

        def device_attr(attr_name: Union[str, tuple[str]]):
            """
            # Device Attribute
            Decorator for device attributes. This is used to change the class's initializer to define the device's attribute to either take in the parameter of the attribute device's value or the device's identifier.
            If the value is passed into the constructor of the class, the value will be used to create the lower device's instance and registered in the global store. If the identifier or an instance of the lower device
            is passed into the constructor of the class, no extra operation will be performed and the decorated class will be instantiated as normal.
            NOTE: This decorated should be used once per class or else the behavior is not guaranteed.

            Args:
                attr_name (str|tuple[str]): the name of the attribute/s to change the type of

            Returns:
                (callable) the decorated function on the device that will be wrapping the class
            """
            if isinstance(attr_name, str):
                attr_name = (attr_name,)

            def class_wrapper(cls):
                original_init = cls.__init__
                # check if the original init needs _indentifer to allow nesting of class decorators
                needsIdentifier = (
                    "_identifier" in inspect.signature(original_init).parameters
                )

                def new_init(self, _identifier: str, **kwargs):
                    parser = DEVICE_PARSERS[device_name]

                    def convert_value(key, value):
                        if check_only_class_instance(value) or key not in attr_name:
                            return value
                        elif isinstance(value, str):
                            if value in UNIQUE_COMPONENT_IDENTIFIERS:
                                return value
                            elif value in parser.store:
                                parser.register_device(value, parser.store[value])
                                return value

                            raise ValueError(f"{device_name}: {value} does not exist")
                        # when an attribute's parameter is passed in as an attribute value
                        newDevice = parser.parse_device(value, _identifier=_identifier)
                        newKey = f"{_identifier}.{key}"
                        parser.register_device(newKey, newDevice)
                        return newKey

                    new_kwargs = {
                        key: convert_value(key, value)
                        for (key, value) in kwargs.items()
                    }
                    if needsIdentifier:
                        new_kwargs["_identifier"] = _identifier

                    original_init(self, **new_kwargs)

                cls.__init__ = new_init
                return cls

            return class_wrapper

        return device_action, device_attr

    return (
        create_masked_device,
        device_parser,
    )


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
                f"{key} is not registered in the device parser list. Skipping..."
            )
            continue
        parser = DEVICE_PARSERS[key]
        for key, device_attr in config.items():
            logging.info(f"Configuring {key}...")
            device = parser.parse_device(device_attr, _identifier=key)
            parser.register_device(key, device)

    logging.info("Device configuration complete")
    logging.info("Total of %s device parsers configured", len(DEVICE_PARSERS))
    logging.debug("Device parsers: \n%s", "\n".join(DEVICE_PARSERS.keys()))
    logging.info(
        "Total of %s devices configured",
        sum([len(x.store) for x in DEVICE_PARSERS.values()]),
    )
    logging.debug(
        "Devices: \n%s",
        "\n".join(
            [
                f"{z}:{w}"
                for z, w in {
                    f'"{x}"': "\n\t\t"
                    + "\n\t\t".join(
                        [
                            f'"{i}":{j}'
                            for i, j in y.store.items()
                            if y.stored_keys is None or i in y.stored_keys
                        ]
                    )
                    + (
                        "\n\t\t masked devices: " + str(y.stored_keys)
                        if y.stored_keys is not None
                        else ""
                    )
                    for x, y in DEVICE_PARSERS.items()
                }.items()
            ]
        ),
    )


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
        device_parser (callable): function to parse the device from config,
        devcie_attr (callable): decorator for higher level device attributes
    """
    create_device, device_parser = create_generic_device_store(
        component_name, component_classes, parser_func
    )
    device_action, device_attr = create_device(component_name)
    return device_action, device_parser, device_attr
