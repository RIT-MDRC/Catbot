#include "src/Pressure/Pressure.h"
#include "src/Handshake/Handshake.h"

// pins
#define COMPRESSOR_PIN 6 // D6
#define PRESSURE_SENSOR_PIN A3 // Analog
#define HANDSHAKE_PIN 4 //  D4

// Operating range of the compressor/pressure system
#define MIN_VOLTAGE 0.33 // at <MIN_PSI> psi
#define MAX_VOLTAGE 2.98 // at <MAX_PSI> psi
#define MIN_PSI 0
#define MAX_PSI 150

// constants for pressure
#define IDEAL_PRESSURE 70 // average pressure we want to maintain

// Resolution to set the ADC to
#define RESOLUTION_BITS 12

// Pressure level that we need to hit to be able to flex the leg (in psi)
// If the psi is higher than this value the handshake will be set high
#define SUFFICIENT_PRESSURE 70

#define PRESSURE_RANGE 10

Pressure systemPressure(PRESSURE_SENSOR_PIN, COMPRESSOR_PIN, RESOLUTION_BITS, IDEAL_PRESSURE, SUFFICIENT_PRESSURE, MIN_PSI, MAX_PSI, PRESSURE_RANGE);
Handshake handshake(HANDSHAKE_PIN);

void setup()
{
  Serial.begin(9600);
  analogReadResolution(RESOLUTION_BITS);
  pinMode(LED_BUILTIN, OUTPUT);
  systemPressure.init();
  handshake.init();
}

void loop()
{
  systemPressure.pressurize(false);
  handshake.setStatus(!systemPressure.pressureOk());
  digitalWrite(LED_BUILTIN, !systemPressure.pressureOk());
  Serial.println(systemPressure.pressureOk(), handshake.getStatus());
  delay(100);
}
