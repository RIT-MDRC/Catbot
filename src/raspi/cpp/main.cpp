#include <iostream>
#include <pigpio.h>

#include "io_controller/motor.h"

#define PIN_PWM 16
#define PIN_DIR 20

int main() 
{
    if (gpioInitialise() < 0) return 1;

    Motor *motor = new Motor(PIN_PWM, PIN_DIR);
    motor->run(true, 30);
    
    time_sleep(5);

    gpioTerminate();
    return 0;
}