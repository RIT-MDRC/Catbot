#include "potentiometer.h"

#define ADC_I2C_ADDR 0x43   // TODO: change this to the real I2C address of the ADC
#define MAX_ROTATION 285    // Range of rotation of the potentiometer.

Potentiometer::Potentiometer(int index) {
    this->index = index;
    
    gpioSetMode(index, PI_OUTPUT);
}

float Potentiometer::getDegrees() {
    
    gpioGetMode()
}