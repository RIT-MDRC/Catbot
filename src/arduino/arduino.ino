#include <DS1307RTC.h>
#include <TimeLib.h>
#include <Time.h>
#include "components/Pressure.cpp"
#include "comms/handshake.cpp"

// pins
#define COMPRESSOR_PIN 7
#define VALVE_1_PIN 8
#define PRESSURE_SENSOR_PIN A0 // Analog
#define COMP_SWITCH_PIN 11     // button #1
#define VALVE_1_SWITCH_PIN 10  // button #2
#define HANDSHAKE_PIN 6

// Operating range of the compressor/pressure system
#define MIN_VOLTAGE 0.5 // at <MIN_PSI> psi
#define MAX_VOLTAGE 4.5 // at <MAX_PSI> psi
#define MIN_PSI 2
#define MAX_PSI 100

// constants for pressure
#define IDEAL_PRESSURE 65 // average pressure we want to maintain

#define TIME_DURATION_FOR_VALVE_OPEN 5 // seconds

// Resolution to set the ADC to
#define RESOLUTION_BITS 10

// Pressure level that we need to hit to be able to flex the leg (in psi)
#define SUFFICIENT_PRESSURE 50

int currentPressure = 0; // (in psi)

int timeWhenValveOpened;
Pressure *systemPressure = NULL;
Handshake *handshake = NULL;

void setup()
{
  Serial.begin(9600);
  systemPressure = new Pressure(PRESSURE_SENSOR_PIN, COMPRESSOR_PIN, RESOLUTION_BITS, IDEAL_PRESSURE, SUFFICIENT_PRESSURE, MIN_PSI, MAX_PSI, MIN_VOLTAGE, MAX_VOLTAGE);
  handshake = new Handshake(HANDSHAKE_PIN);
}

void loop()
{
  systemPressure->Pressurize(compSwitchPressed() && !valveSwitchPressed());
  handshake->setStatus(systemPressure->PressureOk());
  Serial.println(systemPressure->getPressure());
  delay(100);
}

/**
 * Returns compressor button status
 */
bool compSwitchPressed()
{
  return digitalRead(COMP_SWITCH_PIN) == HIGH;
}

/**
 * Returns valve button status
 */
bool valveSwitchPressed()
{
  return digitalRead(VALVE_1_SWITCH_PIN) == HIGH;
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
    digitalWrite(VALVE_1_PIN, HIGH);
  }
  else if ((timeWhenValveOpened + TIME_DURATION_FOR_VALVE_OPEN < now()) || (compSwitchPressed() && valveSwitchPressed()))
  {
    timeWhenValveOpened = NULL;
    digitalWrite(VALVE_1_PIN, LOW);
  }
}
