#include "io_controller/motor.h"

int main() {
    gpioInitialise();

    Motor m(4, 0);
    m.run(false, 50);

    time_sleep(30);
}