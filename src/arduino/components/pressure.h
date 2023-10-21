class Pressure
{
public:
    Pressure(
        uint8_t sensorPin,
        uint8_t compressorPin,
        float IDEAL_PRESSURE,
        float PRESSURE_TOLERANCE,
        float P_MIN, float P_MAX,
        int VOLTAGE_CONST) : sensorPin(sensorPin),
                             compressorPin(compressorPin),
                             IDEAL_PRESSURE(IDEAL_PRESSURE),
                             PRESSURE_TOLERANCE(PRESSURE_TOLERANCE),
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
    const int PRESSURE_TOLERANCE;

    int compressorPin;
    int sensorPin;
    float pressure;
};