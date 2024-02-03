#include "limitSwitch.h"
#define PIN 4

LimitSwitch::LimitSwitch(){
    // TODO: Not implemented
    gpioSetAlertFunc(PIN, executeCallbacks);
}

void LimitSwitch::addCallback(void* func){
    callbackCount++;
    *(callbacks + callbackCount) = func;
}

void LimitSwitch::executeCallbacks(int gpio, int level, uint32_t tick){
    for(int i = 0; i < callbackCount; i++) {
        *(callbacks + i)(level)//(params)
    }
}


