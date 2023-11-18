#include <Arduino.h>

#include "pressure.h"

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
  int max_read_value = pow(2, RESOLUTION_BITS);
  Pressure::pressure = map(analogRead(PRESSURE_SENSOR_PIN), max_read_value * 0.1, max_read_value*0.9, P_MIN, P_MAX);
  return Pressure::pressure;
}

/**
 * Returns true if pressure is within tolerance of the ideal pressure
 */
bool Pressure::pressureOk()
{
  getPressure();
  return (pressure >= SUFFICIENT_PRESSURE);
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
  digitalWrite(COMPRESSOR_PIN, (pressure < IDEAL_PRESSURE || override));
}
