class Pressure
{
public:
    Pressure(uint8_t sensorPin, uint8_t compressorPin, float PRESSURE_UPPER_BOUND, float PRESSURE_LOWER_BOUND, int VOLTAGE_CONST) : sensorPin(sensorPin), compressorPin(compressorPin), PRESSURE_UPPER_BOUND(PRESSURE_UPPER_BOUND), PRESSURE_LOWER_BOUND(PRESSURE_LOWER_BOUND), VOLTAGE_CONST(VOLTAGE_CONST) {}
    float getPressure();
    bool PressureOk();
    void Pressurize(bool override);

private:
    const float PRESSURE_UPPER_BOUND;
    const float PRESSURE_LOWER_BOUND;
    const int VOLTAGE_CONST;

    int compressorPin;
    int sensorPin;
    float pressure;
};