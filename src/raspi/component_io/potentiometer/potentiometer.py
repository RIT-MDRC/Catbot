import adc_receiver

# Max rotation of the potentiometer (degrees)
POT_MAX_DEG : float = 285

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
        reading = adc_receiver.read(self.pot_channel)
        rotation = (reading / 4096.0) * POT_MAX_DEG
        return rotation