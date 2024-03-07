import inspect
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from functools import reduce, wraps
from typing import Union


@dataclass
class Context:
    allowed_classes: list
    parse_device: callable
    store: dict
    stored_keys: set
    masked_device_contexts: list


DEVICE_CONTEXT_COLLECTION: dict[str, Context] = dict()


def check_only_class_instance(ctx: Context, x: any):
    return reduce(lambda res, y: res or isinstance(x, y), ctx.allowed_classes, False)


def register_device(ctx: Context, name: str, device):
    if not check_only_class_instance(ctx, device):
        raise ValueError(
            f"Must be a identifier(string) or "
            + "/".join([x.__name__ for x in ctx.allowed_classes])
        )
    if name in ctx.stored_keys:
        raise ValueError(f"{name} already exists")
    if name in ctx.store and device == ctx.store[name]:
        ctx.stored_keys.add(name)
    ctx.store[name] = device


def create_generic_context(
    generic_device_name: str, device_classes: list, parser_func: callable = None
):
    ctx = Context(
        allowed_classes=device_classes,
        parse_device=parser_func,
        store=dict(),
        stored_keys=set(),
        masked_device_contexts=list(),
    )
    DEVICE_CONTEXT_COLLECTION[generic_device_name] = ctx
    return ctx


def create_context(
    generic_device_name: str, device_classes: list, parser_func: callable = None
):
    return create_generic_context(generic_device_name, device_classes, parser_func)


def create_masked_context(ctx: Context, device_name: str):
    new_ctx = Context(
        allowed_classes=ctx.allowed_classes,
        parse_device=ctx.parse_device,
        store=ctx.store,
        stored_keys=set(),
        masked_device_contexts=list(),
    )
    ctx.masked_device_contexts.append(device_name)
    DEVICE_CONTEXT_COLLECTION[device_name] = new_ctx
    return new_ctx


def get_context(device_name: str):
    return DEVICE_CONTEXT_COLLECTION.get(device_name, None)


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


def device_action(ctx: Context):
    def decorator(func: callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if len(args) < 1:
                raise ValueError("Missing argument")
            if not check_only_class_instance(ctx, args[0]):
                raise ValueError(
                    "First argument must be a identifier(string) or "
                    + "/".join([x.__name__ for x in ctx.allowed_classes])
                )
            value = ctx.store.get(args[0]) if isinstance(args[0], str) else args[0]
            return func(value, *args[1:], **kwargs)

        return wrapper

    return decorator


def device_attr(ctx: Context, attr_name: Union[str, tuple[str]]):
    if isinstance(attr_name, str):
        attr_name = (attr_name,)

    def class_wrapper(cls):
        original_init = cls.__init__
        # check if the original init needs _indentifer to allow nesting of class decorators
        needsIdentifier = "_identifier" in inspect.signature(original_init).parameters

        def new_init(self, _identifier: str, **kwargs):
            def convert_value(key, value):
                if check_only_class_instance(ctx, value) or key not in attr_name:
                    return value
                elif isinstance(value, str):
                    if value in ctx.stored_keys:
                        return value
                    elif value in ctx.store:
                        register_device(ctx, value, ctx.store[value])
                        return value

                    raise ValueError(
                        f"{ctx}: {value} does not exist. Unique identifiers: \n{ctx.stored_keys}"
                    )
                # when an attribute's parameter is passed in as an attribute value
                newDevice = ctx.parse_device(value, _identifier=_identifier)
                newKey = f"{_identifier}.{key}"
                register_device(ctx, newKey, newDevice)
                return newKey

            new_kwargs = {
                key: convert_value(key, value) for (key, value) in kwargs.items()
            }
            if needsIdentifier:
                new_kwargs["_identifier"] = _identifier

            original_init(self, **new_kwargs)

        cls.__init__ = new_init
        return cls

    return class_wrapper


def open_json(file_name: str = "pinconfig.json"):
    with open(file_name, "r") as file:
        config = json.load(file, object_pairs_hook=OrderedDict)
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
        ctx = get_context(key)
        if ctx is None:
            logging.warning(
                f"{key} is not registered in the device parser list. Skipping..."
            )
            continue
        for key, device_attr in config.items():
            logging.info(f"Configuring {key}...")
            device = ctx.parse_device(device_attr, _identifier=key)
            register_device(ctx, key, device)

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
                        [
                            f'"{i}":{j}'
                            for i, j in y.store.items()
                            if y.stored_keys is None or i in y.stored_keys
                        ]
                    )
                    for x, y in DEVICE_CONTEXT_COLLECTION.items()
                }.items()
            ]
        ),
    )
