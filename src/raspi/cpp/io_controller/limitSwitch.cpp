#include "limitSwitch.h"
#define PIN 4

#define MAX_CALLBACKS 5

typedef void (*gpioAlertFunc_t) (int gpio, int level, uint32_t tick);

LimitSwitch::LimitSwitch(){
    callbacks[MAX_CALLBACKS];
    callbackCount = 0;
    

    // gpioSetAlertFunc(PIN,
    // &[this](int gpio, int level, uint32_t tick) {
    //     return executeCallbacks(gpio, level, tick);
    // }
    );
}

void LimitSwitch::addCallback(LimitSwitchEvent event){
    callbackCount++;
    *(callbacks + callbackCount) = event;
}

void LimitSwitch::executeCallbacks(int gpio, int level, uint32_t tick){
    for(int i = 0; i < callbackCount; i++) {
        (*(callbacks + i))(level);
        //(((callbacks + i)))(level);//(params)
    }
}


