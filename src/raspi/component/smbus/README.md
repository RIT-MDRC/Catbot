# SMBUS

## parser input

- bus: int

## Diagram Representation
![Smbus Model](https://github.com/user-attachments/assets/46b97e53-46e2-44da-8a7e-11f1bd9a8b7f)

## Helper Methods

### write_byte
type: write_byte(smbus2: SMBus, address, value) -> None

Write a byte to the smbus2 device.

Args:
  - smbus2 (SMBus): the smbus2 device
  - address (int): the address to write to
  - value (list[int]): the value to write
  - start_register (int): the register to start writing to

---
### read_byte
type: read_byte(smbus2: SMBus, address, length=1) -> int

Read bytes from the smbus2 device.

Args:
  - smbus2 (SMBus): SMBus device to use
  - address (int): I2C address of the device
  - start_register (int): index of the register to start reading from
  - length (int, optional): legnth of the data to read. Defaults to 1.

Returns:
  - int: data read from the device

---
### i2c_wrrd
type: i2c_wrrd(smbus2: SMBus, address, write_data, read_length) -> list

Write and read data from the smbus2 device.

Args:
  - smbus2 (SMBus): the smbus2 device
  - address (int): the address to write to
  - write_data (list[int]): the data to write
  - read_length (int): the length of the data to read

Returns:
  - list: the data read from the device

---
### i2c_rdwr
type: i2c_rdwr(smbus2: SMBus, *actions) -> list

Write and read data from the smbus2 device. 
@see SMBus2.i2c_rdwr

Args:
  - smbus2 (SMBus): the smbus2 device
  - address (int): the address to write to
  - write_data (list[int]): the data to write
  - read_length (int): the length of the data to read

Returns:
  - list: the data read from the device
