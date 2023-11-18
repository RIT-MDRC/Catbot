#include "handshake.h"

void Handshake::toggle()
{
  status = !status;
  digitalWrite(pin, status);
}

void Handshake::setHigh()
{
  setStatus(true);
}

void Handshake::setLow()
{
  setStatus(false);
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