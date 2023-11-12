class Handshake
{
public:
  Handshake(int pin) : pin(pin)
  {
    pinMode(pin, OUTPUT);
  }
  void toggle();
  void setHigh();
  void setLow();
  void setStatus(bool status);
  bool getStatus();

private:
  bool status = false;
  int pin;
};