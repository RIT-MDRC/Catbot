#include "motor.h"
#include <boost/python.hpp>

Motor::Motor(int pwmPin, int latchAddress) {
    // gpioInitialise();   // TODO: put this somewhere else later

    this->pwmPin = pwmPin;
    this->latchAddress = latchAddress;

    gpioSetMode(pwmPin, PI_OUTPUT);
    
    gpioSetMode(PIN_DIR_ADR0, PI_OUTPUT);
    gpioSetMode(PIN_DIR_ADR1, PI_OUTPUT);
    gpioSetMode(PIN_DIR_ADR2, PI_OUTPUT);
    gpioSetMode(PIN_MOTOR_DIR, PI_OUTPUT);
    gpioSetMode(PIN_LATCH_EN, PI_OUTPUT);

    gpioSetPWMfrequency(pwmPin, PWM_FREQUENCY);
}

void Motor::run(bool clockwise, int speed) {
    if (speed < 0 || speed > PWM_RANGE)
        throw std::invalid_argument("speed [" + std::to_string(speed) + "] is not valid");

    if (latchAddress >= 8)
        throw std::invalid_argument("latch addr [" + std::to_string(latchAddress + "] invalid; must fit in 3 bits"))

    uint_8 addressBits[] = { (latchAddress >> 0) & 1, (latchAddress >> 1) & 1, (latchAddress >> 2) & 1 };

    for (int i = 0; i < 3; i++)
        gpioWrite(LATCH_ADDRESS_PINS[i], addressBits[i]);

    gpioWrite(PIN_MOTOR_DIR, clockwise ? 0 : 1);  // TODO: test to make sure that the direction is actually correct
    gpioWrite(PIN_LATCH_EN, 0);
    gpioWrite(PIN_LATCH_EN, 1);
    gpioPWM(pwmPin, speed);
}

void Motor::stop() {
    gpioPWM(pwmPin, 0);
}

BOOST_PYTHON_MODULE(motor) {
    using namespace boost::python;
    class_<Motor>("Motor", init<int, int>())
        .def("run", &Motor::run)
        .def("stop", &Motor::stop);
}