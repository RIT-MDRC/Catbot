class Pressure
{
public:
    Pressure(
        uint8_t PRESSURE_SENSOR_PIN,
        uint8_t COMPRESSOR_PIN,
        int RESOLUTION_BITS,
        float IDEAL_PRESSURE,
        float SUFFICIENT_PRESSURE,
        float P_MIN, float P_MAX) : PRESSURE_SENSOR_PIN(PRESSURE_SENSOR_PIN),
                                            COMPRESSOR_PIN(COMPRESSOR_PIN),
                                            RESOLUTION_BITS(RESOLUTION_BITS),
                                            IDEAL_PRESSURE(IDEAL_PRESSURE),
                                            SUFFICIENT_PRESSURE(SUFFICIENT_PRESSURE),
                                            P_MAX(P_MAX),
                                            P_MIN(P_MIN)
    {
    }
    float getPressure();
    bool pressureOk();
    void pressurize(bool override);

private:
    const float IDEAL_PRESSURE;
    const int P_MAX;
    const int P_MIN;
    const int PRESSURE_SENSOR_PIN;
    const int RESOLUTION_BITS;
    const int COMPRESSOR_PIN;

    const int SUFFICIENT_PRESSURE;

    float pressure;
};