#include "Pressure.h"

/**
 * Returns pressure in PSI
 */
float Pressure::getPressure()
{
  int max_read_value = pow(2, _RESOLUTION_BITS);
  _pressure = map(analogRead(_PRESSURE_SENSOR_PIN), max_read_value * 0.1, max_read_value * 0.9, _P_MIN, _P_MAX);
  return _pressure;
}

Pressure::Pressure(
    uint8_t PRESSURE_SENSOR_PIN,
    uint8_t COMPRESSOR_PIN,
    int RESOLUTION_BITS,
    float IDEAL_PRESSURE,
    float SUFFICIENT_PRESSURE,
    float P_MIN, float P_MAX, int PRESSURE_RANGE)
{
  this->_PRESSURE_SENSOR_PIN = PRESSURE_SENSOR_PIN;
  this->_COMPRESSOR_PIN = COMPRESSOR_PIN;
  this->_RESOLUTION_BITS = RESOLUTION_BITS;
  this->_IDEAL_PRESSURE = IDEAL_PRESSURE;
  this->_SUFFICIENT_PRESSURE = SUFFICIENT_PRESSURE;
  this->_P_MAX = P_MAX;
  this->_P_MIN = P_MIN;
  this->_PRESSURE_RANGE = PRESSURE_RANGE;
}

void Pressure::init()
{
  pinMode(_PRESSURE_SENSOR_PIN, INPUT);
  pinMode(_COMPRESSOR_PIN, OUTPUT);
  getPressure();
}

/**
 * Returns true if pressure is within tolerance of the ideal pressure
 */
bool Pressure::pressureOk()
{
  getPressure();
  if (_pressure < _IDEAL_PRESSURE - _PRESSURE_RANGE || _pressure > _IDEAL_PRESSURE){
    _pressurizing = _pressure < _IDEAL_PRESSURE;
  }
  return (_pressure >= _IDEAL_PRESSURE);
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
  pressureOk();
  digitalWrite(_COMPRESSOR_PIN, (_pressurizing || override));
}
