#include <packet.h>

// Packages up some data to send across an I2C bus
class Packager
{
    public:
        void Main();
    private:
        void Send(Packet *packet);
};