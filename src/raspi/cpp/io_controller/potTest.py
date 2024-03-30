import potentiometer
import pigpio
from time import sleep

def main():
	x = potentiometer.Potentiometer(0, 0)

	while(True):
		print(x.getDegrees())
		sleep(0.01)

main()