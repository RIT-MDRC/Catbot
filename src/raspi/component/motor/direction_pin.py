from state_management.generic_devices import create_output_device_component

direction_pin_action, direction_pin_attr = create_output_device_component(
    "directionPin"
)

__all__ = ["direction_pin_attr", "set_direction", "check_direction"]


@direction_pin_action
def check_direction(directionPin, direction) -> bool:
    if direction not in [0, 1]:
        raise ValueError("direction must be either 0 or 1")
    return directionPin.value == direction


@direction_pin_action
def set_direction(directionPin, direction) -> bool:
    if direction not in [0, 1]:
        raise ValueError("direction must be either 0 or 1")
    directionPin.value = direction
    return True


@direction_pin_action
def get_direction(directionPin) -> int:
    return directionPin.value
