class Pressure
{
public:
    Pressure(
        uint8_t sensorPin,
        uint8_t compressorPin,
        float IDEAL_PRESSURE,
        float IDEAL_PRESSURE_RANGE,
        float P_MIN, float P_MAX,
        int VOLTAGE_CONST) : sensorPin(sensorPin),
                             compressorPin(compressorPin),
                             IDEAL_PRESSURE(IDEAL_PRESSURE),
                             IDEAL_PRESSURE_RANGE(IDEAL_PRESSURE_RANGE),
                             P_MIN(P_MIN),
                             P_MAX(P_MAX),
                             VOLTAGE_CONST(VOLTAGE_CONST) {}
    float getPressure();
    bool PressureOk();
    void Pressurize(bool override);

private:
    const float IDEAL_PRESSURE;
    const float P_MIN;
    const float P_MAX;
    const int VOLTAGE_CONST;
    const int IDEAL_PRESSURE_RANGE;

    int compressorPin;
    int sensorPin;
    float pressure;
};