#include <pigpio.h>
#include <cmath>

#define I2C_BUS 1
#define ADC_I2C_ADDR 0x48
#define ADC_RESOLUTION_BITS 12
#define MAX_ROTATION 285.0    // Range of rotation of the potentiometer, in degrees.

class Potentiometer {

    public:
        /**
         * Creates an instance of a potentiometer. There should only be one instance of this per real-world potentiometer.
         * index: The index of this potentiometer [0-7]. This is labeled on the circuit board as POT0, POT1, ...
        */
        Potentiometer(int index);
        /**
         * Gets the current rotation of the potentiometer.
         * returns: The current rotation of the potentiometer, in degrees [0-285].
        */
        unsigned int getDegrees();

    private:
        static int adcHandle;
        int index;

        // 4 most significant bits for ADC command byte, used to select channel (see page 11
        // of https://www.ti.com/lit/ds/symlink/ads7828.pdf). Index 0 represents bits sent for potentiometer at CH0,
        // index 1 represents bits sent for potentiometer at CH1, and so on.
        const uint8_t CHANNEL_TO_ADDR_MAP[8] = {
            0b1000,  // CH0
            0b1100,  // CH1
            0b1001,  // ...
            0b1101,
            0b1010,
            0b1110,
            0b1011,
            0b1111   // CH7
        };
};