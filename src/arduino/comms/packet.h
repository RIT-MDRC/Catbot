class Packet
{
    public:
        int GetPacketType();
        int GetDataLength();
        int *GetData();
        int AddByte(int byte);
        int AddBytes(int *bytes);
    private:
        int packetType;
        int *data;
};