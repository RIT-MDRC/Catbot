#include "handshake.h"

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
void Handshake::toggle()
{
  status = !status;
  digitalWrite(pin, status);
}

void Handshake::setHigh()
{
  status = true;
  digitalWrite(pin, status);
}

void Handshake::setLow()
{
  status = false;
  digitalWrite(pin, status);
}

void Handshake::setStatus(bool status)
{
  this->status = status;
  digitalWrite(pin, status);
}

bool Handshake::getStatus()
{
  return status;
}