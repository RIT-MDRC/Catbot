# Version 1 supervised hardware action. ROS clocks must be synchronized (chrony).
# stamp is inference-request time, so queued inference is included in action age.
builtin_interfaces/Time stamp
string session
uint64 sequence
catbot_interfaces/ActuatorPositionCommand command
