from smbus2 import SMBus

# The I2C address of the ADC
ADC_I2C_ADDR = 0x49
I2C_BUS = 1

# Index is the channel ID (CH0, CH1, ...), element at that index is the set of channel selection
# bits needed to retrieve data at that channel
CHANNEL_SELECTIONS = [0b000, 0b100, 0b001, 0b101, 0b010, 0b110, 0b011, 0b111]

# Open I2C connection on bus 1
with SMBus(1) as bus:
    # selection_bits = CHANNEL_SELECTIONS[pot_channel] << 4
    # command_byte = 0b10001100 | selection_bits
    command_byte = int(0b11001100)

    while True:
        try:
            bytes_array = bus.read_i2c_block_data(ADC_I2C_ADDR, command_byte, 2)

            most_significant = bytes_array[0]
            least_significant = bytes_array[1]

            most_significant = (most_significant << 4) | (most_significant >> 4)
            least_significant = (least_significant << 4) | (most_significant >> 4)

            reading = (most_significant << 8) + least_significant

            print(f"received : {reading} / {bin(reading)}")
        except Exception:
            print("failed to read, trying again...")
            continue  # just try again

