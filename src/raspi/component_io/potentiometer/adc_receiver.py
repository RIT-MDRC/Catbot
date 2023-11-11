from smbus2 import SMBus

# The I2C address of the ADC, which we will need to poll to get potentiometer data
# Currently an arbitrary value, will likely need to be changed.
ADC_I2C_ADDR = 0x09

# Index is the channel ID (CH0, CH1, ...), element at that index is the set of channel selection
# bits needed to retrieve data at that channel
CHANNEL_SELECTIONS = [0b000, 0b100, 0b001, 0b101, 0b010, 0b110, 0b011, 0b111]

def read(channel : int) -> int:
    """
    Get the reading of the potentiometer connected to the given
    channel of the ADC. Returns a value [0, 4096)
    """
    result = 0

    # Open I2C connection on bus 1
    with SMBus(1) as bus:
        selection_bits = CHANNEL_SELECTIONS[channel] << 4
        command_byte = 0b10001100 | selection_bits

        while True:
            try:
                result = bus.read_word_data(ADC_I2C_ADDR, command_byte)
            except Exception:
                print("Failed to read, trying again...")
                continue  # just try again
            break

    return result