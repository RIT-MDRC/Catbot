#include <iostream>
#include <pigpio.h>

int main() 
{
    if (gpioInitialise() < 0) return 1;

    

    return 0;
}