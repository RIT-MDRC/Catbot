from smbus2 import SMBus

# The I2C address of the ADC, which we will need to poll to get potentiometer data
# Currently an arbitrary value, will likely need to be changed.
ADC_I2C_ADDR = 0x09

# Index is the channel ID (CH0, CH1, ...), element at that index is the set of channel selection
# bits needed to retrieve data at that channel
CHANNEL_SELECTIONS = [0b000, 0b100, 0b001, 0b101, 0b010, 0b110, 0b011, 0b111]

# Max rotation of the potentiometer (degrees)
POT_MAX_DEG : float = 285

# Number of bits of resolution in our ADC
ADC_RESOLUTION_BITS = 10

class Potentiometer():
    """
    Represents a potentiometer that tracks the current abduction/adduction rotation
    of each leg.
    """
    pot_channel : int
    reading : int = 0  # Raw potentiometer reading, ranges [0, 4096)

    def __init__(self, pot_channel : int) -> None:
        """
        Initialize a new instance of a potentiometer. There should only be
        one Potentiometer instance for each real-world potentiometer.

        :param pot_channel: ADC channel the potentiometer is connected to
        """
        self.pot_channel = pot_channel

    def get_rotation(self) -> float:
        """
        Get the rotation (in degrees) for the potentiometer with this object's `pot_channel`. Also updates
        the `reading` attribute with the unsanitized potentiometer reading, should it be needed.
        """
        # Open I2C connection on bus 1
        with SMBus(1) as bus:
            selection_bits = CHANNEL_SELECTIONS[self.pot_channel] << 4
            command_byte = 0b10001100 | selection_bits

            while True:
                try:
                    reading = bus.read_word_data(ADC_I2C_ADDR, command_byte)
                except Exception:
                    print("Failed to read, trying again...")
                    continue  # just try again
                break

        rotation = (reading / (2 ** ADC_RESOLUTION_BITS)) * POT_MAX_DEG
        return rotation