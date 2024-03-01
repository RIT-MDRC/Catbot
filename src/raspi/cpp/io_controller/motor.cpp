#include "motor.h"
#include <boost/python.hpp>
Motor::Motor(int pwmPin, int directionPin) {
    this->pwmPin = pwmPin;
    this->directionPin = directionPin;

    gpioSetMode(pwmPin, PI_OUTPUT);
    gpioSetMode(directionPin, PI_OUTPUT);
    gpioSetPWMfrequency(pwmPin, PWM_FREQUENCY);
}

void Motor::run(bool clockwise, int speed) {
    if (speed < 0 || speed > PWM_RANGE)
        throw std::invalid_argument("speed [" + std::to_string(speed) + "] is not valid");

    gpioWrite(directionPin, clockwise ? 0 : 1); // TODO: need to test which is clockwise
    gpioPWM(pwmPin, speed);
}

void Motor::stop() {
    gpioPWM(pwmPin, 0);
}

BOOST_PYTHON_MODULE(motor){
    using namespace boost::python;
    class_<Motor>("Motor", init<std::int, std::int>())
        .def("run", &Motor::run)
        .def("stop", &Motor::stop)
        .def_readonly("pwmPin", &Motor::pwmPin)
        .def_readonly("directionPin", &Motor::directionPin)
}