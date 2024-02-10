#include <pigpio.h>

typedef void (*LimitSwitchEvent)(int);

class LimitSwitch {
    public:
        /**
        *Creates a new limit switch. Subscribes the pin to the gpioAlerts.
        */
        LimitSwitch();

        /**
        *adds a callback to call
        */
        void addCallback(LimitSwitchEvent event);

        
    private:
        static void executeCallbacks(int gpio, int level, unsigned int tick);
        LimitSwitchEvent* callbacks;
        int callbackCount;

};