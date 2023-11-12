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
  double voltage = (analogRead(PRESSURE_SENSOR_PIN) / pow(2, RESOLUTION_BITS)) * 5.0; // Volts
  Pressure::pressure = (((voltage - MIN_VOLTAGE) * PRESSURE_RANGE) / VOLTAGE_RANGE) + P_MIN;
  return Pressure::pressure;
}

/**
 * Returns true if pressure is within tolerance of the ideal pressure
 */
bool Pressure::PressureOk()
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
void Pressure::Pressurize(bool override)
{
  getPressure();

  if (pressure < IDEAL_PRESSURE || override)
  { // First check if system pressure is too high, turn off compressor
    digitalWrite(COMPRESSOR_PIN, HIGH);
  }
  else
  {
    digitalWrite(COMPRESSOR_PIN, LOW);
  }
}
