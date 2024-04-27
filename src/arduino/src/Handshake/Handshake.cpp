#include "Handshake.h"

Handshake::Handshake(uint8_t pin)
{
  this->_pin = pin;
  // init();
}

void Handshake::init()
{
  pinMode(_pin, OUTPUT);
}

void Handshake::toggle()
{
  status = !status;
  digitalWrite(_pin, status);
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
  digitalWrite(_pin, status);
}

bool Handshake::getStatus()
{
  return status;
}