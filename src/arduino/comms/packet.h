class Packet
{
    public:
        int GetPacketType();
        int GetDataLength();
        int *GetData();
    private:
        int packetType;
        int dataLength;
        int *data;
};