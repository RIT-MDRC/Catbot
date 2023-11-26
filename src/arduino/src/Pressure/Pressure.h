#pragma once

#include <Arduino.h>

class Pressure
{
public:
    Pressure(){};
    Pressure(
        uint8_t PRESSURE_SENSOR_PIN,
        uint8_t COMPRESSOR_PIN,
        int RESOLUTION_BITS,
        float IDEAL_PRESSURE,
        float SUFFICIENT_PRESSURE,
        float P_MIN, float P_MAX);
    void init();
    float getPressure();
    bool pressureOk();
    void pressurize(bool override);

private:
    unsigned int _RESOLUTION_BITS;
    unsigned int _SUFFICIENT_PRESSURE;
    unsigned int _IDEAL_PRESSURE;
    unsigned int _P_MAX;
    int _P_MIN;
    int _PRESSURE_SENSOR_PIN;
    int _COMPRESSOR_PIN;

    float _pressure;
};
