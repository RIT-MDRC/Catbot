class Pressure
{
public:
    Pressure(
        uint8_t PRESSURE_SENSOR_PIN,
        uint8_t COMPRESSOR_PIN,
        int RESOLUTION_BITS,
        float IDEAL_PRESSURE,
        float SUFFICIENT_PRESSURE,
        float P_MIN, float P_MAX,
        int MIN_VOLTAGE, int MAX_VOLTAGE) : PRESSURE_SENSOR_PIN(PRESSURE_SENSOR_PIN),
                                            COMPRESSOR_PIN(COMPRESSOR_PIN),
                                            RESOLUTION_BITS(RESOLUTION_BITS),
                                            IDEAL_PRESSURE(IDEAL_PRESSURE),
                                            SUFFICIENT_PRESSURE(SUFFICIENT_PRESSURE),
                                            PRESSURE_RANGE(P_MAX - P_MIN),
                                            P_MIN(P_MIN),
                                            VOLTAGE_RANGE(MAX_VOLTAGE - MIN_VOLTAGE),
                                            MIN_VOLTAGE(MIN_VOLTAGE)
    {
    }
    float getPressure();
    bool PressureOk();
    void Pressurize(bool override);

private:
    const float IDEAL_PRESSURE;
    const int PRESSURE_RANGE;
    const int VOLTAGE_RANGE;
    const int MIN_VOLTAGE;
    const int P_MIN;
    const int PRESSURE_SENSOR_PIN;
    const int RESOLUTION_BITS;
    const int COMPRESSOR_PIN;

    const int SUFFICIENT_PRESSURE;

    float pressure;
};