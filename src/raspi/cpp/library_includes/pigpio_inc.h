#include "environment.h"

#ifdef ROBOT
#include <pigpio.h>
#endif

#ifdef COMPUTER
#include "pigpio_sub.h"
#endif