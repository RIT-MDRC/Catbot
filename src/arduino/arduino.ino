#include <DS1307RTC.h>
#include <TimeLib.h>
#include <Time.h>
#include "components/Pressure.h"

// pins
#define COMPRESSORPIN 9
#define VALVE_1PIN 8
#define SENSORPIN A0        // Analog
#define COMP_SWITCHPIN 11   // button #1
#define VALVE1_SWITCHPIN 10 // button #2

// constants
#define VOLTAGE_CONST 5
#define P_MAX 145 // psi
#define P_MIN 0

#define SYSTEM_PRESSURE 82    // average pressure we want to maintain
#define PRESSURE_TOLERANCE 10 // tolerance for pressure (we want to maintain in the difference margin of 3 psi)

#define TIME_DURATION_FOR_VALVE_OPEN 5 // seconds

int timeWhenValveOpened;
Pressure *systemPressure = NULL;

void setup()
{
  Serial.begin(9600);
  systemPressure = &Pressure(SENSORPIN, COMPRESSORPIN, SYSTEM_PRESSURE, PRESSURE_TOLERANCE, P_MIN, P_MAX, VOLTAGE_CONST);
}

void loop()
{
  systemPressure->Pressurize(compSwitchPressed() && !valveSwitchPressed());
  valveControl();
  Serial.print(systemPressure->getPressure());
  delay(100);
}

/**
 * Returns compressor button status
 */
bool compSwitchPressed()
{
  return digitalRead(COMP_SWITCHPIN) == HIGH;
}

/**
 * Returns valve button status
 */
bool valveSwitchPressed()
{
  return digitalRead(VALVE1_SWITCHPIN) == HIGH;
}

/**
 * Opens or closes the valve based on time and active button
 *
 * LOGIC:
 * If the valve button is pressed and valve is not open:
 *   the valve will open
 * else if valve is opened for more than TIME_DURATION_FOR_VALVE_OPEN or both button is pressed:
 *   the valve will close
 * else:
 *   No op
 */
void valveControl()
{
  if (!compSwitchPressed() && valveSwitchPressed() && timeWhenValveOpened == NULL)
  { // If valve switch is pressed open valve
    timeWhenValveOpened = now();
    digitalWrite(VALVE_1PIN, HIGH);
  }
  else if ((timeWhenValveOpened + TIME_DURATION_FOR_VALVE_OPEN < now()) || (compSwitchPressed() && valveSwitchPressed()))
  {
    timeWhenValveOpened = NULL;
    digitalWrite(VALVE_1PIN, LOW);
  }
}
