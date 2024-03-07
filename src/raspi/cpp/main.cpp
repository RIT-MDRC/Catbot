#include "io_controller/potentiometer.h"
#include <iostream>

int main() {
    Potentiometer pot(5);

    while (true) {
        std::cout << pot.getDegrees() << std::endl;
        time_sleep(0.01);
    }    
}