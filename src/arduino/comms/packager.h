#include <pressure.h>
#include <potentiometer.h>
#include <packet.h>
// TODO: docstring
class Packager
{
    public:
        void Main();
    private:
        Pressure *pressure;
        Potentiometer **potentiometers;
        PotentiometerEntry *potentiometerHistory;
        void Send(Packet *packet);
};

struct PotentiometerEntry
{
    int id;
    int *potValues;
};
