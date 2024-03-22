from state_management import create_masked_context, device_action, output_device_ctx

ctx = create_masked_context(output_device_ctx, "directionPin")


@device_action(ctx)
def check_direction(directionPin, direction) -> bool:
    if direction not in [0, 1]:
        raise ValueError("direction must be either 0 or 1")
    print(directionPin.value)
    return directionPin.value == direction


@device_action(ctx)
def set_direction(directionPin, direction) -> bool:
    if direction not in [0, 1]:
        raise ValueError("direction must be either 0 or 1")
    directionPin.value = direction
    return True


@device_action(ctx)
def get_direction(directionPin) -> int:
    return directionPin.value
