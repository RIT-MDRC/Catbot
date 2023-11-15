from unittest.mock import MagicMock
from gpiozero import InputDevice, OutputDevice


class FakeOutputDevice(MagicMock):
    def __init__(self, pin: int):
        super().__init__(OutputDevice)
        self.pin = pin
        self.value = 0

    def on(self):
        self.value = 1

    def off(self):
        self.value = 0

    def toggle(self):
        self.value = 1 - self.value

    def is_active(self):
        return self.value == 1


class FakeInputDevice(MagicMock):
    pin = 0
    when_activated = None
    when_deactivated = None

    def __init__(self, pin: int):
        super().__init__(InputDevice)
        self.pin = pin
        self.value = 0

    def is_active(self):
        return self.value == 1

    def toggle(self):
        self.value = 1 - self.value
        print(f"(Dev) toggling input device value to {self.value}")
        if self.value == 1 and self.when_activated is not None:
            print("(Dev) calling when_activated")
            self.when_activated()
        elif self.value == 0 and self.when_deactivated is not None:
            print("(Dev) calling when_deactivated")
            self.when_deactivated()
