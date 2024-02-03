#include <pigpio.h>

class Potentiometer {

    public:
        /**
         * Creates an instance of a potentiometer. There should only be one instance of this per real-world potentiometer.
         * index: The index of this potentiometer [0-7], as defined by the analog-to-digital converter.
        */
        Potentiometer(int index);
        /**
         * Gets the current rotation of the potentiometer.
         * returns: The current rotation of the potentiometer, in degrees [0-285].
        */
        int getDegrees();

    private:
        int index;
};