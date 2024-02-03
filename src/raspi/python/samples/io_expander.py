import RPI.GPIO as GPIO

def detect(pin):
    print("limit switch hit")

GPIO.setmode(GPIO.BCM)
GPIO.setup(25, GPIO.IN)

GPIO.add_event_detect(25, GPIO.RISING, callback=detect, bouncetime=100)

input()