#pragma once

#include <Arduino.h>

class Handshake
{
public:
  Handshake(){};
  Handshake(uint8_t pin);
  void init();
  void toggle();
  void setHigh();
  void setLow();
  void setStatus(bool status);
  bool getStatus();

private:
  bool status = false;
  int _pin;
};
