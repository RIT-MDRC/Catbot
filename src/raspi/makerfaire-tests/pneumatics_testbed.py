# Pneumatics Testbed
#
# Throwaway program for driing pneumatics pins
#
#

from gpiozero import PWMOutputDevice
from time import sleep


pin_id = input("Enter Pin Number: ")
while(pin_id != -1)
    test_pin = DigitalOutputDevice(pin_id) # set pin
    val = input("Enter value: ")
    if(val == 1):
        test_pin.On()
        print("Pin set HIGH")
    else:
        test_pin.Off()
        print("Pin set LOW")
    sleep(0.5)
    pin_id = input("Enter Pin Number: ")

    
    




