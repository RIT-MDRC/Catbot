#pragma once

#include <Arduino.h>

class Handshake
{
private:
  bool status = false;
  uint8_t _pin;

public:
  Handshake(){};
  Handshake(uint8_t pin);
  void init();
  void toggle();
  void setHigh();
  void setLow();
  void setStatus(bool status);
  bool getStatus();
};
