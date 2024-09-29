# Analog to Digital Converter(ADC)

## Description

Electrical component that takes in 8 analog inputs and reads each one. [Hardware doc](https://drive.google.com/open?id=1gvnOic5LwNqlCqx-z4vHShFm0rJplFgQ&disco=AAABJ0xEwNY)

## Diagram Representation

![ADC Model](https://github.com/user-attachments/assets/e184328c-c3e1-42c0-8fc9-af0a66af8463)

The software will create configured analog input pins during parsing and creates analog input classes which can be used to read the values of the analog signal.
The created analog input classes can then be treated as if a generic analog input class objects.

## Parser

  - address: str = i2c address of the adc (i.e. "0x48" or "48" will be converted to integers)
  - i2c: SMBus = i2c object
  - power_down: str = power down selection (i.e. "0b00" or "10" will be converted to integers)
  - input_devices: dict =
      ```ts
      {
        "name_of_device": int = channel of the device on the adc (0 ~ 7)
        ...
      }
      ```
