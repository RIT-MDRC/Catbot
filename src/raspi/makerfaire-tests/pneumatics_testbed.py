# Pneumatics Testbed
#
# Throwaway program for setting pneumatics pins
#
#

from gpiozero import DigitalOutputDevice
from time import sleep


test_pin = DigitalOutputDevice(10) # set pin
test_pin.value = 1
sleep(5)

#####################################



