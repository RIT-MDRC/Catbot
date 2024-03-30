#include "potentiometer.h"
#include <boost/python.hpp>

Potentiometer::Potentiometer(int index, int adcIndex) {
    this->index = index;
    this->adcIndex = adcIndex;
    
    gpioInitialise();  // TODO: put this somewhere else later, e.g. in the python code during init

    if (ADC_HANDLES[adcIndex] == 0)
        ADC_HANDLES[adcIndex] = i2cOpen(I2C_BUS, ADC_ADDRESSES[adcIndex], 0);
}

unsigned int Potentiometer::getDegrees() {
    char readBuffer[2];

    // 0b1100 represents the least significant bits of the command byte, where 11 is our
    // power-down selection and 00 are placeholders for unused bits.
    uint8_t commandByte = (CHANNEL_TO_ADDR_MAP[index] << 4) | 0b1100;
    i2cWriteByte(ADC_HANDLES[adcIndex], commandByte);

    i2cReadDevice(ADC_HANDLES[adcIndex], readBuffer, 2);

    uint16_t reading = (readBuffer[0] << 8) + readBuffer[1];
    unsigned int degrees = (reading / pow(2, ADC_RESOLUTION_BITS)) * MAX_ROTATION;
    return degrees;
}


BOOST_PYTHON_MODULE(potentiometer){
    using namespace boost::python;
    class_<Potentiometer>("Potentiometer", init<int, int>())
        .def("getDegrees", &Potentiometer::getDegrees);
}