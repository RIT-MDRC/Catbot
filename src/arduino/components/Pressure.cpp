#include "pressure.h"

float Pressure::getPressure()
{
  double sensorRead = analogRead(sensorPin) * 0.0049;                                                                                                             // Volts
  double pressure = (((sensorRead - 0.1 * VOLTAGE_CONST) * (PRESSURE_UPPER_BOUND - PRESSURE_LOWER_BOUND)) / (0.8 * VOLTAGE_CONST)) + PRESSURE_LOWER_BOUND + 0.36; // PSI
  Pressure::pressure = pressure;
  return pressure;
}

bool Pressure::PressureOk()
{
  return (pressure >= PRESSURE_LOWER_BOUND && pressure <= PRESSURE_UPPER_BOUND);
}

/**
 * Turns compressor on or off
 *
 * LOGIC:
 * if pressure is less than SYSTEM_PRESSURE or override is true:
 *   turn on compressor
 * else:
 *   turn off compressor
 */
void Pressure::Pressurize(bool override)
{
  getPressure();

  if (pressure < PRESSURE_UPPER_BOUND || override)
  { // First check if system pressure is too high, turn off compressor
    digitalWrite(compressorPin, HIGH);
  }
  else
  {
    digitalWrite(compressorPin, LOW);
  }
}
