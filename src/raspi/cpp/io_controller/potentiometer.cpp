#include "potentiometer.h"
#include <boost/python.hpp>

int Potentiometer::adcHandles[] = { 0, 0 };
int Potentiometer::adcAddresses[] = { 0x48, 0x48 };

Potentiometer::Potentiometer(int index, int adcIndex) {
    this->index = index;
    this->adcIndex = adcIndex;
    
    gpioInitialise();  // TODO: put this somewhere else later, e.g. in the python code during init

    if (Potentiometer::adcHandle[adcIndex] == 0)
        Potentiometer::adcHandle[adcIndex] = i2cOpen(I2C_BUS, adcAddresses[adcIndex], 0);
}

unsigned int Potentiometer::getDegrees() {
    char readBuffer[2];

    // 0b1100 represents the least significant bits of the command byte, where 11 is our
    // power-down selection and 00 are placeholders for unused bits.
    uint8_t commandByte = (CHANNEL_TO_ADDR_MAP[index] << 4) | 0b1100;
    i2cWriteByte(Potentiometer::adcHandle, commandByte);

    i2cReadDevice(Potentiometer::adcHandle, readBuffer, 2);

    unsigned int degrees = (reading / pow(2, ADC_RESOLUTION_BITS)) * MAX_ROTATION;
    return degrees;
}


BOOST_PYTHON_MODULE(potentiometer){
    using namespace boost::python;
    class_<Potentiometer>("Potentiometer", init<int, int>())
        .def("getDegrees", &Potentiometer::getDegrees);
}