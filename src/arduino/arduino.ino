#include "components/Pressure.cpp"
#include "comms/handshake.cpp"

// pins
#define COMPRESSOR_PIN 12
#define VALVE_1_PIN 8
#define PRESSURE_SENSOR_PIN A0 // Analog
#define HANDSHAKE_PIN 6

// Operating range of the compressor/pressure system
#define MIN_VOLTAGE 0.33 // at <MIN_PSI> psi
#define MAX_VOLTAGE 2.98 // at <MAX_PSI> psi
#define MIN_PSI 2
#define MAX_PSI 150

// constants for pressure
#define IDEAL_PRESSURE 80 // average pressure we want to maintain

// Resolution to set the ADC to
#define RESOLUTION_BITS 12

// Pressure level that we need to hit to be able to flex the leg (in psi)
#define SUFFICIENT_PRESSURE 50

Pressure *systemPressure = NULL;
Handshake *handshake = NULL;

void setup()
{
  Serial.begin(9600);
  analogReadResolution(RESOLUTION_BITS);
  systemPressure = new Pressure(PRESSURE_SENSOR_PIN, COMPRESSOR_PIN, RESOLUTION_BITS, IDEAL_PRESSURE, SUFFICIENT_PRESSURE, MIN_PSI, MAX_PSI, MIN_VOLTAGE, MAX_VOLTAGE);
  handshake = new Handshake(HANDSHAKE_PIN);
}

void loop()
{
  systemPressure->Pressurize(false);
  handshake->setStatus(systemPressure->PressureOk());
  Serial.println(systemPressure->getPressure());
  delay(100);
}
