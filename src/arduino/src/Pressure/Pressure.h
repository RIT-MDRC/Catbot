#pragma once

#include <Arduino.h>

class Pressure
{
private:
    unsigned int _RESOLUTION_BITS;
    unsigned int _SUFFICIENT_PRESSURE;
    unsigned int _IDEAL_PRESSURE;
    unsigned int _P_MAX;
    int _P_MIN;
    uint8_t _PRESSURE_SENSOR_PIN;
    uint8_t _COMPRESSOR_PIN;
    int _PRESSURE_RANGE;

    float _pressure;
    float _pressurizing;

public:
    Pressure(){};
    Pressure(
        uint8_t PRESSURE_SENSOR_PIN,
        uint8_t COMPRESSOR_PIN,
        int RESOLUTION_BITS,
        float IDEAL_PRESSURE,
        float SUFFICIENT_PRESSURE,
        float P_MIN, float P_MAX,
        int PRESSURE_RANGE);
    void init();
    float getPressure();
    bool pressureOk();
    void pressurize(bool override);
};
