from dataclasses import field
from src.raspi.state_management.device import register_device
from src.raspi.state_management.generic_devices.generic_devices import output_device_ctx
from src.raspi.state_management.utils.deviceMock import FakeDigitalInputDevice, value_change


class PinProxy(): #please feel free rename this if this is a bad name
 
    pin: int
    is_active: bool
    name: str
    addr: int

    when_activated: None
    when_deactivated: None

    _identifier: str = field(default=name)
    

    def when_activated_fn():
        return
    
    def when_deactivated_fn():
        return


    # device = Latch(**data)

    def __init__(self, device, addr, name):
        self.device = device
        self.addr = addr
        self.pin = addr
        self.name = name
        self.is_active = False
        self.when_activated = self.when_activated_fn
        self.when_deactivated = self.when_deactivated_fn

    @value_change
    def on(self):
        self.is_active = True

    @value_change
    def off(self):
        self.is_active = False

    
    @property
    def is_active(self):
        return self.is_active


    def parse_device():

        device = None

        if output_device_ctx is None:
            raise ValueError(
                "No output device parser found. Makesure to define output device before the latch"
            )
        if not PinProxy in output_device_ctx.allowed_classes: #Self reference may not work
            output_device_ctx.allowed_classes = (
                PinProxy,
                *output_device_ctx.allowed_classes,
            )
        for identifier, addr in device.pins.items():
            dev_identifier = f"{device._identifier}.{identifier}"
            #     _identifier = pin id in the json
            virtualDevice = PinProxy(device, addr)
            register_device(output_device_ctx, dev_identifier, virtualDevice)

    
