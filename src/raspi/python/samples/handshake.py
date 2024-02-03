from time import sleep
from gpiozero import DigitalInputDevice
from gpiozero import DigitalOutputDevice


handshake = DigitalInputDevice(27)
compressor = DigitalOutputDevice(22)

while(1):
    print("Value: " + str(handshake.value),end="\r")
    compressor.value = handshake.value


