#include <pigpio.h>

class LimitSwitch {
    public:
        /**
        *Creates a new limit switch. Subscribes the pin to the gpioAlerts.
        */
        LimitSwitch();

        /**
        *adds a callback to call
        */
        void addCallback(void* func);
    private:
        void executeCallbacks(int gpio, int level, unsigned int tick);
        void** callbacks;
        int callbackCount;

};