#include "potentiometer.h"
#include <boost/python.hpp>

Potentiometer::Potentiometer(int adcHandle, int index) {
    this->adcHandle = adcHandle;
    this->index = index;
    
    gpioSetMode(index, PI_OUTPUT);
}

unsigned int Potentiometer::getDegrees() {
    char readBuffer[2];

    // 0b1100 represents the least significant bits of the command byte, where 11 is our
    // power-down selection and 00 are placeholders for unused bits.
    uint8_t commandByte = (CHANNEL_SELECTION_MSB[index] << 4) + 0b1100;
    i2cWriteByte(adcHandle, commandByte);

    i2cReadDevice(adcHandle, readBuffer, 2);

    uint16_t reading = (readBuffer[0] << 8) + readBuffer[1];
    unsigned int degrees = (reading / pow(2, ADC_RESOLUTION_BITS)) * MAX_ROTATION;

    return degrees;
}