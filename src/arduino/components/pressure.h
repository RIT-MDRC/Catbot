class Pressure
{
    public:
        Pressure();
        bool PressureOk();
        void Pressurize();
    private:
        const float PRESSURE_UPPER_BOUND;
        const float PRESSURE_LOWER_BOUND;

        int pin;
        float pressure;
};