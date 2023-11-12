from smbus2 import SMBus



def read(channel : int) -> int:
    """
    Get the reading of the potentiometer connected to the given
    channel of the ADC. Returns a value [0, 4096)
    """
    