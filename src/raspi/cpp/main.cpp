#include <iostream>
#include <pigpio.h>

#include "io_controller/motor.h"
#include "io_controller/potentiometer.h"

void testEvent(int gpio, int level, uint32_t tick) {
    std::cout << "level " << level << std::endl; 
}

void testEvent2(int gpio, int level, uint32_t tick) {
    std::cout << "test  3 " << level << std::endl; 
}

void testPot() {
    int handle = i2cOpen(I2C_BUS, ADC_I2C_ADDR, 0);
    Potentiometer pot(handle, 1);

    while (true) {
        std::cout << pot.getDegrees() << std::endl;
        time_sleep(0.01);
    }
}

int main()  {
    if (gpioInitialise() < 0) return 1;

    std::cout << "gpio initialized" << std::endl;

    //testPot();

    gpioTerminate();
    return 0;
}