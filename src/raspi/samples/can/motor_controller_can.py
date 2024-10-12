import can
import cantools
import math
import time

# initialize can messages and bus
db = cantools.database.load_file("src/raspi/odrive-cansimple.dbc")
print(db.messages)

bus = can.Bus("can0", bustype = "socketcan")
# Flush CAN RX buffer so there are no more old pending messages
# while not (bus.recv(timeout=0) is None): pass

axisID = 0x0

# create message
print("\nRequesting AXIS_STATE_FULL_CALIBRATION_SEQUENCE (0x03) on axisID: " + str(axisID))
msg = db.get_message_by_name('Set_Axis_State')
data = msg.encode({'Axis_Requested_State': 0x03})
msg = can.Message(arbitration_id = msg.frame_id | axisID << 5, is_extended_id = False, data = data)
print(db.decode_message('Set_Axis_State', msg.data))
print(msg)

# send message
try:
    bus.send(msg)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent!  Please verify can0 is working first")

print("Waiting for calibration to finish...")
# Read messages infinitely and wait for the right ID to show up
# Specifically, wait for a heartbeat message that indicates the motor controller is idle
while True:
    msg = bus.recv()
    if msg.arbitration_id == ((axisID << 5) | db.get_message_by_name('Heartbeat').frame_id):
        current_state = db.decode_message('Heartbeat', msg.data)['Axis_State']
        print("Heartbeat came with state " + str(current_state))
        if current_state.value == 0x1:
            print("\nAxis has returned to Idle state.")
            break
#    else:
#        print("Message with id " + str(msg.arbitration_id) + " received.")

# Waits for the next heartbeat message, checks if there was an error
for msg in bus:
    if msg.arbitration_id == ((axisID << 5) | db.get_message_by_name('Heartbeat').frame_id):
        msgData = db.decode_message('Heartbeat', msg.data)
        errorCode = msgData['Axis_Error']
        if errorCode.value == 0x00:
            print("No errors")
        else:
            print("Axis error!  Error code: "+str(hex(errorCode.value)))
            data = db.encode_message('Get_Motor_Error', {'Motor_Error': 0x01})
            msg = can.Message(arbitration_id= (axisID << 5) | db.get_message_by_name('Get_Motor_Error').frame_id, is_extended_id=False, data=data)
            try:
                bus.send(msg)
                print("Message sent on {}".format(bus.channel_info))
            except can.CanError:
                print("Message NOT sent!")
        break
#    else:
#        print("Message with id " + str(msg.arbitration_id) + " received.")
#        print(msg)

# Send message for placing controller in closed loop control
print("\nPutting axis",axisID,"into AXIS_STATE_CLOSED_LOOP_CONTROL (0x08)...")
data = db.encode_message('Set_Axis_State', {'Axis_Requested_State': 0x08})
msg = can.Message(arbitration_id= 0x07 | axisID << 5, is_extended_id=False, data=data)
print(msg)

try:
    bus.send(msg)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent!")

# Wait for heartbeat to check if state was changed
for msg in bus:
    if msg.arbitration_id == 0x01 | axisID << 5:
        print("\nReceived Axis heartbeat message:")
        msg = db.decode_message('Heartbeat', msg.data)
        print(msg)
        if msg['Axis_State'].value == 0x8:
            print("Axis has entered closed loop")
        else:
            print("Axis failed to enter closed loop")
        break
#    else:
#        print("Message with id " + str(msg.arbitration_id) + " received.")

target = 0
#print("eror pls" + bus)
data = db.encode_message('Set_Limits', {'Velocity_Limit':10.0, 'Current_Limit':10.0})
msg = can.Message(arbitration_id=axisID << 5 | 0x00F, is_extended_id=False, data=data)
bus.send(msg)

t0 = time.monotonic()
while True:
    setpoint = 2.0 * math.sin((time.monotonic() - t0)*2)
    print("goto " + str(setpoint))
    data = db.encode_message('Set_Input_Pos', {'Input_Pos':setpoint, 'Vel_FF':0.0, 'Torque_FF':0.0})
    msg = can.Message(arbitration_id=axisID << 5 | 0x00C, data=data, is_extended_id=False)
    bus.send(msg)
    time.sleep(0.01)
