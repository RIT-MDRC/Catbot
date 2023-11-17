from smbus2 import SMBus

pot_channel = int(input("input pot channel [0-7]: "))

# The I2C address of the ADC
ADC_I2C_ADDR = 0x49

# Index is the channel ID (CH0, CH1, ...), element at that index is the set of channel selection
# bits needed to retrieve data at that channel
CHANNEL_SELECTIONS = [0b000, 0b100, 0b001, 0b101, 0b010, 0b110, 0b011, 0b111]

# Open I2C connection on bus 1
with SMBus(1) as bus:
    selection_bits = CHANNEL_SELECTIONS[pot_channel] << 4
    command_byte = 0b10001100 | selection_bits

    while True:
        try:
            reading = bus.read_word_data(ADC_I2C_ADDR, command_byte)
        except Exception:
            print("failed to read, trying again...")
            continue  # just try again
        break

print(f"received value : {reading}")