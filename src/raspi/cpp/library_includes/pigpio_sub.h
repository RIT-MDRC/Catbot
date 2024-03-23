#define PI_INPUT 0
#define PI_OUTPUT 1
#define PI_ALT0 4
#define PI_ALT1 5
#define PI_ALT2 6
#define PI_ALT3 7
#define PI_ALT4 3
#define PI_ALT5 2

#define PI_FILE_READ 1
#define PI_FILE_WRITE 2
#define PI_FILE_RW 3

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