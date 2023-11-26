#include "Pressure.h"

/**
 * Returns pressure in PSI
 *
 * LOGIC:
 * 1. Read sensor value
 * 2. Convert sensor value to voltage
 * 3. Convert voltage to pressure
 * 4. Set pressure
 * 5. Return pressure
 */
float Pressure::getPressure()
{
  int max_read_value = pow(2, _RESOLUTION_BITS);
  Pressure::_pressure = map(analogRead(_PRESSURE_SENSOR_PIN), max_read_value * 0.1, max_read_value * 0.9, _P_MIN, _P_MAX);
  return Pressure::_pressure;
}

Pressure::Pressure(
    uint8_t PRESSURE_SENSOR_PIN,
    uint8_t COMPRESSOR_PIN,
    int RESOLUTION_BITS,
    float IDEAL_PRESSURE,
    float SUFFICIENT_PRESSURE,
    float P_MIN, float P_MAX)
{
  this->_PRESSURE_SENSOR_PIN = PRESSURE_SENSOR_PIN;
  this->_COMPRESSOR_PIN = COMPRESSOR_PIN;
  this->_RESOLUTION_BITS = RESOLUTION_BITS;
  this->_IDEAL_PRESSURE = IDEAL_PRESSURE;
  this->_SUFFICIENT_PRESSURE = SUFFICIENT_PRESSURE;
  this->_P_MAX = P_MAX;
  this->_P_MIN = P_MIN;
  init();
}

void Pressure::init()
{
  pinMode(_PRESSURE_SENSOR_PIN, INPUT);
  pinMode(_COMPRESSOR_PIN, OUTPUT);
}

/**
 * Returns true if pressure is within tolerance of the ideal pressure
 */
bool Pressure::pressureOk()
{
  getPressure();
  return (_pressure >= _SUFFICIENT_PRESSURE);
}

/**
 * Turns compressor on or off
 *
 * LOGIC:
 * if pressure is less than IDEA_PRESSURE or override is true:
 *   turn on compressor
 * else:
 *   turn off compressor
 */
void Pressure::pressurize(bool override)
{
  getPressure();
  digitalWrite(_COMPRESSOR_PIN, (_pressure < _IDEAL_PRESSURE || override));
}
