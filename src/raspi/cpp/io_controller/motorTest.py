from gpiozero import PWMOutputDevice
from time import sleep

pwm1 = PWMOutputDevice(4)
pwm2 = PWMOutputDevice(17)
pwm3 = PWMOutputDevice(18)
pwm4 = PWMOutputDevice(27)
pwm5 = PWMOutputDevice(13)
pwm6 = PWMOutputDevice(19)
pwm7 = PWMOutputDevice(16)
pwm8 = PWMOutputDevice(26)
sleep(0.1)

pwm1.value = 0.1
pwm2.value = 0.1
pwm3.value = 0.1
pwm4.value = 0.1
pwm5.value = 0.1
pwm6.value = 0.1
pwm7.value = 0.1
pwm8.value = 0.1
sleep(5)