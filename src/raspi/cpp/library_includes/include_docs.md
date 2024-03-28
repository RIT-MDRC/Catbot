# INCLUDE DOCS
## environment.h
This will define either ROBOT or COMPUTER depending on the architecture. If it is a linux os with an ARM architeture,  it will define ROBOT, otherwise it will define COMPUTER.

## *_inc.h
This is the file that you will include in other files. It will contain a ROBOT and COMPUTER section. When ROBOT is defined, it will include the pi specific library. When COMPUTER is defined, it will include a custom substitution file. You need to create a new inc.h and sub.h file for each new pi library you want to use.

```
#include "environment.h"

#ifdef ROBOT
#include <pigpio.h>
#endif

#ifdef COMPUTER
#include "pigpio_sub.h"
#endif
```

## *_sub.h
This is the substitution file that will contain all methods and definitions from the pi library that are needed in any class that includes this.

```
#define PI_FILE_APPEND 4
#define PI_FILE_CREATE 8
#define PI_FILE_TRUNC 16

//gpio unsigned int [0-53]
//mode unsigned int [0-7]
static void gpioSetMode(unsigned int gpio, unsigned int mode) { }

//user_gpio unsigned int [0-31]
//frequency unsigned int [5Hz-40KHz]
static void gpioSetPWMfrequency(unsigned int user_gpio, unsigned int frequency) { }

//user_gpio unsigned int [0-31]
//dutycycle unsigned int [0-255]
static void gpioPWM(unsigned int user_gpio, unsigned int dutycycle) { }
```
