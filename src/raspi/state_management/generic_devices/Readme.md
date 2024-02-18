# GENERIC DEVICE
last updated: 2024-2-17
by @hiromon0125

## Description
This folder contains the generic devices that can be used in the IO controller. Mostly all of the different kinds of GPIO pins.

## Definition
The term "generic" is used to describe the devices that are not specific to any particular device. The generic devices can be used to control other devices that are connected to the GPIO pins of the Raspberry Pi. In OOP terms, the generic devices can be thought of a base class that can be inherited by other devices to control the GPIO pins. However, since the class in itself is not directly inherited and just being reused and renamed as another component, this document will use the word "renamed" instead of "inherit" to describe the process of creating a new device from the generic device.

## Why use generic devices?
The generic devices can be used to easily create a new device that is carbon copy of one another. For example, components that only rely on one GPIO pin for control can just be renamed to create a new component. This allows the developer to create a new component without having to write the same code again and again. There is also another benefit of using generic devices. When the developer creates a new component from the generic device and renames it, the store of the generic device is used to store the renamed device's state. This can be beneficial because we can declare the renamed device in the generic device's section of the pinconfig file and when the renamed device is used as a property of another component, the statemanager will automatically create a store for the renamed device. This keeps the pinconfig file short and clean and less annoying for electrical to swap pin configuration. This does not mean that renamed devices stored in the generic device's store cannot be used as a property of another component. The renamed device can only be grabbed in the actions declared for the renamed device and error is thrown. This acts as a isolated store for the renamed devices during runtime but shared during configuration parsing/setup.

## Generic Input Device
The input device is just a single GPIO pin of the Raspberry Pi.
The input device can be used to read the state of the GPIO pin.
Example devices that uses this are:
- pressure sensor

### Methods
* create_input_device_component: allows the developer to create a renamed input device component with an isolated store.

## Generic Output Device
The output device is just a single GPIO pin of the Raspberry Pi.
The output device can be used to set the state of the GPIO pin.
Example devices that uses this are:
- LED
- Relay
- Compressor
- Valve

### Methods
* create_output_device_component: allows the developer to create a renamed output device component with an isolated store.

## Generic PWM Output Device
The PWM output device is just a single GPIO pin of the Raspberry Pi. The PWM output device can be used to set the state of the GPIO pin with a PWM signal.
Example devices that uses this are:
- Servo motor

### Methods
* create_pwm_output_device_component: allows the developer to create a renamed PWM output device component with an isolated store.

## Why not declare action methods for the generic devices?
The action methods for the generic devices are purposely not implemented as a safety procausion. Although in the future this may change, if the generic device's action methods are used instead of renamed device's actions, the developer can accidentally use the wrong renamed device for the wrong action. This can lead to unexpected behavior and a hazard. The developer should always use the renamed device's action methods to control the GPIO pins. As a safety procausion each masked devices must have their own action methods.