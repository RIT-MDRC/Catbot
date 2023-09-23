class Potentiometer
{
    public:
        Potentiometer(int id);
        int GetId();
        int GetValue();
        LimitStatus GetLimitStatus();
    private:
        int id;
        int value;
        LimitStatus limitStatus;
};

enum LimitStatus { NEGATIVE_LIMIT, NOT_AT_LIMIT, POSITIVE_LIMIT };