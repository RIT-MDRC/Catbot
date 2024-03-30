import motor
from time import sleep

def main():
    m = motor.Motor(13, 2)
    m.run(0, 50)
    sleep(20)


main()