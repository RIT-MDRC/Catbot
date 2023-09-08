class Packet
{
    public:
        int GetRequestType();
        int GetDataLength();
        int *GetData();
        int AddByte(int byte);
        int AddBytes(int *bytes);
    private:
        int requestType;
        int dataLength;
        int *data;
};