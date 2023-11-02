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
  double sensorRead = analogRead(sensorPin) * 0.0049;                                                                // Volts
  double pressure = (((sensorRead - 0.1 * VOLTAGE_CONST) * (P_MAX - P_MIN)) / (0.8 * VOLTAGE_CONST)) + P_MIN + 0.36; // PSI
  Pressure::pressure = pressure;
  return pressure;
}

/**
 * Returns true if pressure is within tolerance of the ideal pressure
 */
bool Pressure::PressureOk()
{
  return (pressure >= IDEAL_PRESSURE - IDEAL_PRESSURE_RANGE);
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
    digitalWrite(compressorPin, HIGH);
  }
  else
  {
    digitalWrite(compressorPin, LOW);
  }
}
