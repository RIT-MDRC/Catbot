import inspect
import json
import logging
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from functools import reduce, wraps

from .utils.logger import configure_logger


@dataclass
class Context:
    allowed_classes: list
    parse_device: callable
    store: dict
    stored_keys: set
    masked_device_contexts: list
    on_exit: callable
    masked_from: "Context" = None


DEVICE_CONTEXT_COLLECTION = {}


def check_only_class_instance(ctx: Context, x: any):
    return reduce(lambda res, y: res or isinstance(x, y), ctx.allowed_classes, False)


def register_device(ctx: Context, name: str, device):
    if not check_only_class_instance(ctx, device):
        raise ValueError(
            f"{device} must be a identifier(string) or "
            + "/".join([x.__name__ for x in ctx.allowed_classes])
        )
    if name in ctx.stored_keys:
        raise ValueError(f"{name} already exists")
    ctx.store[name] = device
    ctx.stored_keys.add(name)


def create_generic_context(
    generic_device_name: str,
    device_classes: list,
    parser_func: callable = None,
    on_exit: callable = None,
):
    if isinstance(device_classes, list):
        device_classes = tuple(device_classes)
    if not isinstance(device_classes, tuple):
        device_classes = (device_classes,)
    ctx = Context(
        allowed_classes=device_classes,
        parse_device=parser_func,
        store=dict(),
        stored_keys=set(),
        masked_device_contexts=list(),
        on_exit=on_exit,
    )
    DEVICE_CONTEXT_COLLECTION[generic_device_name] = ctx
    return ctx


def create_context(
    generic_device_name: str,
    device_classes: list,
    parser_func: callable = None,
    on_exit: callable = None,
):
    return create_generic_context(
        generic_device_name, device_classes, parser_func, on_exit
    )


def create_masked_context(ctx: Context, device_name: str):
    new_ctx = Context(
        allowed_classes=ctx.allowed_classes,
        parse_device=ctx.parse_device,
        store=ctx.store,
        stored_keys=set(),
        masked_device_contexts=list(),
        on_exit=ctx.on_exit,
        masked_from=ctx,
    )
    ctx.masked_device_contexts.append(device_name)
    DEVICE_CONTEXT_COLLECTION[device_name] = new_ctx
    return new_ctx


def get_context(device_name: str) -> Context:
    """NOTE: This function will not throw if context is missing. Returns None instead."""
    logging.debug(f"Getting context for {device_name}")
    ctx = DEVICE_CONTEXT_COLLECTION.get(device_name, None)
    return ctx


def device_parser(ctx: Context):
    def decorator(func: callable):
        def wrapped_func(value, _identifier):
            if isinstance(value, dict):
                value["_identifier"] = _identifier
            device = func(value)
            return device

        ctx.parse_device = wrapped_func
        for sub_context in ctx.masked_device_contexts:
            DEVICE_CONTEXT_COLLECTION[sub_context].parse_device = wrapped_func
        return wrapped_func

    return decorator


def device_exit(ctx: Context):
    def decorator(func: callable):
        ctx.on_exit = func
        return func

    return decorator


def device_action(ctx: Context):
    def decorator(func: callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if len(args) < 1:
                raise ValueError("Missing argument")
            if not (
                check_only_class_instance(ctx, args[0]) or isinstance(args[0], str)
            ):
                raise ValueError(
                    f"First argument({args[0]}) must be a identifier(string) or "
                    + "/".join([x.__name__ for x in ctx.allowed_classes])
                )
            value = ctx.store.get(args[0]) if isinstance(args[0], str) else args[0]
            if value is None and isinstance(args[0], str):
                raise ValueError(f"{args[0]} not found in {ctx}")
            return func(value, *args[1:], **kwargs)

        return wrapper

    return decorator


@dataclass(slots=True, frozen=True)
class Identifier:
    ctx: Context


def identifier(ctx: Context):
    """function used to mark an attribute of a class as an identifier for the device decorator to find and correctly parse the device.

    Args:
        ctx (Context): context of where the attribute device is stored

    Returns:
        Identifier: Identifier class that stores the context for the device decorator to find and correctly parse the device.
    """
    return Identifier(ctx)


def device(cls):
    original_init = cls.__init__
    needsIdentifier = "_identifier" in inspect.signature(original_init).parameters
    identifier_attrs = {
        k: v.ctx for k, v in cls.__dict__.items() if isinstance(v, Identifier)
    }

    def new_init(self, _identifier: str = None, **kwargs):
        def convert_value(key, value):
            if key not in identifier_attrs or check_only_class_instance(
                (ctx := identifier_attrs[key]), value
            ):
                # irrelevant attribute values
                return value

            if isinstance(value, str):
                # identifier
                if not value in ctx.store:
                    raise ValueError(
                        f"{ctx}: {value} does not exist. Unique identifiers: \n{ctx.store}"
                    )
                if not value in ctx.stored_keys:
                    ctx.stored_keys.add(value)

                return value

            # when an attribute's parameter is passed in as an attribute value
            newDevice = ctx.parse_device(value, _identifier=_identifier)
            newKey = f"{_identifier}.{key}"
            register_device(ctx, newKey, newDevice)
            return newKey

        new_kwargs = {k: convert_value(k, v) for k, v in kwargs.items()}
        if needsIdentifier:
            new_kwargs["_identifier"] = _identifier
        original_init(self, **new_kwargs)

    cls.__init__ = new_init
    return cls


def open_json(file_name: str = "pinconfig.json"):
    with open(file_name, "r") as file:
        config = json.load(file, object_pairs_hook=OrderedDict)
    for key, value in config.items():
        yield key, value


def log_states():
    logging.info("Device configuration complete")
    logging.info(
        "Total of %s device parsers configured", len(DEVICE_CONTEXT_COLLECTION)
    )
    logging.debug("Device parsers: \n%s", "\n".join(DEVICE_CONTEXT_COLLECTION.keys()))
    logging.info(
        "Total of %s devices configured",
        sum([len(x.store) for x in DEVICE_CONTEXT_COLLECTION.values()]),
    )
    logging.debug(
        "Devices: \n%s",
        "\n".join(
            [
                f"\n{z}:\n\t\t{w}"
                for z, w in {
                    f'"{x}"': "\n\t\t".join(
                        [f'"{i}":{j}' for i, j in y.store.items() if i in y.stored_keys]
                    )
                    for x, y in DEVICE_CONTEXT_COLLECTION.items()
                }.items()
            ]
        ),
    )


@contextmanager
def log_states():
    logging.info("Device configuration complete")
    logging.info(
        "Total of %s device parsers configured", len(DEVICE_CONTEXT_COLLECTION)
    )
    logging.debug("Device parsers: \n%s", "\n".join(DEVICE_CONTEXT_COLLECTION.keys()))
    logging.info(
        "Total of %s devices configured",
        sum([len(x.store) for x in DEVICE_CONTEXT_COLLECTION.values()]),
    )
    logging.debug(
        "Devices: \n%s",
        "\n".join(
            [
                f"\n{z}:\n\t\t{w}"
                for z, w in {
                    f'"{x}"': "\n\t\t".join(
                        [f'"{i}":{j}' for i, j in y.store.items() if i in y.stored_keys]
                    )
                    for x, y in DEVICE_CONTEXT_COLLECTION.items()
                }.items()
            ]
        ),
    )


@contextmanager
def configure_device(
    file_name: str = "pinconfig.json",
    file_kv_generator: callable = open_json,
    log_level: str = "Debug",
):
    """configure the devices from the pinconfig file. This will parse the devices and store them in the global store.

    Args:
        file_name (str, optional): file of the pinconfiguration. Defaults to "pinconfig.json".
        file_kv_generator (callable[[file_name: str], Generator[tuple[str, Any], Any, None]], optional): function for opening the pinconfig. Defaults to open_json.

    Details:
        file_kv_generator is a function that takes in a file name and returns a generator that yields a tuple of the key and the value. This is used to open the pinconfig file and parse the devices.
        The expected behavior is that the file_kv_generator will parse the config and return a generator for the first layer of key and value pairs.
        The key should be the identifier of the device parser and the value should be the object with device identifier and attributes.
        The expected behavior is that the file_kv_generator will parse the config and return a generator for the first layer of key and value pairs.
        The key should be the identifier of the device parser and the value should be the object with device identifier and attributes.

    WARNING:
        This method will skip any parser that was not registered in the device parser list.
        This could happen for two reasons. The device store was not initialized due to the file that the initializer is in was not imported in the script file(memory benefit), or the parser's identifier had a typo in the pinconfig file(Will need to be fixed immediately).
    """
    configure_logger(log_level)
    logging.info("Configuring devices...")
    for key, config in file_kv_generator(file_name):
        ctx = get_context(key)
        if ctx is None:
            logging.warning(f"Context for {key} not found. Skipping...")
            continue
        if ctx.masked_from and (casted_devices := config.get("__cast", None)):
            for masked_key, masked_device_identifier in casted_devices.items():
                if not isinstance(masked_device_identifier, str):
                    raise ValueError(
                        f"Masked device {masked_device_identifier} is not a valid identifier in {ctx}"
                    )
                casting_device = ctx.masked_from.store.get(masked_device_identifier)
                if casting_device is None:
                    raise ValueError(
                        f"Masked device {masked_device_identifier} not found in {ctx.masked_from}"
                    )
                register_device(ctx, masked_key, casting_device)
            del config["__cast"]
        for key, device_attr in config.items():
            device = ctx.parse_device(device_attr, _identifier=key)
            register_device(ctx, key, device)

    log_states()
    logging.info("Device configuration complete")


@contextmanager
def configure_device_w_context(
    file_name: str = "pinconfig.json",
    file_kv_generator: callable = open_json,
    log_level: str = "Debug",
):
    configure_device(
        file_name=file_name, file_kv_generator=file_kv_generator, log_level=log_level
    )

    yield

    logging.info("Exiting system...")
    for ctx in DEVICE_CONTEXT_COLLECTION.values():
        if ctx.on_exit is not None:
            ctx.on_exit()
    logging.info("Successfully Exiting system...")
    logging.shutdown()


@contextmanager
def configure_device_w_context(
    file_name: str = "pinconfig.json",
    file_kv_generator: callable = open_json,
    log_level: str = "Debug",
):
    configure_device(
        file_name=file_name, file_kv_generator=file_kv_generator, log_level=log_level
    )

    yield

    logging.info("Exiting system...")
    for ctx in DEVICE_CONTEXT_COLLECTION.values():
        if ctx.on_exit is not None:
            ctx.on_exit()
    logging.info("Successfully Exiting system...")
    logging.shutdown()
