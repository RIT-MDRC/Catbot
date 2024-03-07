from smbus2 import SMBus
from time import sleep

bus = SMBus(1)

while True:
    b = bus.read_i2c_block_data(0x48, 0b111101100, 2)
    print(b)
    sleep(0.01)