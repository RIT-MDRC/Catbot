#include "handshake.h"

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