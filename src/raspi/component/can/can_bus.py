import can
import cantools
import math
import time
import logging

class CanBus:
    bus: can.Bus
    db: object

    def __init__(self,channel = "can0",interface = "socketcan",config_context = None, ignore_config = False, **kwargs):
        self.db = cantools.database.load_file("src/raspi/odrive-cansimple.dbc")
        self.bus = can.Bus(channel,interface,config_context,ignore_config,**kwargs)
    

# TODO: Move MotorController into it's own file.
class MotorController:
    axis_id: int
    can: CanBus


    def __init__(self, can: CanBus, axis_id: int):
        self.axis_id = axis_id
        self.can = can

    
    def send_message(self, message_name: str, message_data: dict):
        """
        Send a message to this motor controller's can bus.
        """
        # create message
        msg = self.can.db.get_message_by_name(message_name)
        data = msg.encode(message_data)
        msg = self.can.Message(arbitration_id = msg.frame_id | self.axis_id << 5, is_extended_id = False, data = data)
        logging.info(self.can.db.decode_message(message_name, msg.data))
        logging.info(msg)

        # send message
        try:
            self.can.bus.send(msg)
            logging.info("Message sent on {}".format(self.can.bus.channel_info))
        except self.can.CanError:
            logging.error("Message NOT sent!  Please verify can0 is working first")
    

    def receive_single_message(self):
        """
        Recieve a single message (likely not the expected one), depends on how can.recv() works
        """
        msg = self.can.recv()
        logging.info(msg)
        return msg
    
    
    def recieve_message_by_name(self,message_name):
        """
        Receive a message by name from can.recv(), depends on how can.recv() works
        """
        while True:
            msg = self.bus.recv()
            if  msg.arbitration_id == ((self.axis_id << 5) | self.can.bus.db.get_message_by_name(message_name).frame_id):
                logging.info(msg)
                return msg

