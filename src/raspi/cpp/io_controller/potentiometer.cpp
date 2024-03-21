#include "potentiometer.h"
#include <boost/python.hpp>

int Potentiometer::adcHandle = 0;

Potentiometer::Potentiometer(int index) {
    this->index = index;
    
    gpioInitialise();  // TODO: put this somewhere else later

    if (Potentiometer::adcHandle == 0)
        Potentiometer::adcHandle = i2cOpen(I2C_BUS, ADC_I2C_ADDR, 0);
}

unsigned int Potentiometer::getDegrees() {
    char readBuffer[2];

    // 0b1100 represents the least significant bits of the command byte, where 11 is our
    // power-down selection and 00 are placeholders for unused bits.
    uint8_t commandByte = (CHANNEL_TO_ADDR_MAP[index] << 4) | 0b1100;
    i2cWriteByte(Potentiometer::adcHandle, commandByte);

    i2cReadDevice(Potentiometer::adcHandle, readBuffer, 2);

    uint16_t reading = (readBuffer[0] << 8) + readBuffer[1];
    //unsigned int degrees = (reading / pow(2, ADC_RESOLUTION_BITS)) * MAX_ROTATION;

    return reading;
    //return degrees;
}


BOOST_PYTHON_MODULE(potentiometer){
    using namespace boost::python;
    class_<Potentiometer>("Potentiometer", init<int>())
        .def("getDegrees", &Potentiometer::getDegrees);
}