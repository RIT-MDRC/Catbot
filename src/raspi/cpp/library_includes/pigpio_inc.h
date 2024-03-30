#include "environment.h"

#ifdef ROBOT
#include <pigpio.h>
#warning "robot"
#endif

#ifdef COMPUTER
#include "pigpio_sub.h"
#warning "computer"
#endif