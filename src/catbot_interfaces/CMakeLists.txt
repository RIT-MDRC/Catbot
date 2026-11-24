cmake_minimum_required(VERSION 3.8)
project(catbot_interfaces)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ActuatorErrorState.msg"
  "msg/ActuatorKinematicState.msg"
  "msg/ActuatorPositionCommand.msg"
  "msg/BodyErrorState.msg"
  "msg/BodyKinematicState.msg"
  "msg/PolicyFeedback.msg"
  "msg/PolicyMetrics.msg"
  "msg/ClockProbe.msg"
  "msg/ClockReply.msg"
  "msg/PolicyReady.msg"
  "msg/OrinTelemetry.msg"
  "srv/GetSupervisorStatus.srv"
  "msg/PolicyAction.msg"
  "msg/PolicyActionAck.msg"
  "msg/OrinHeartbeat.msg"
  "msg/SupervisorOperatorPrompt.msg"
  "msg/SupervisorHealth.msg"
  "msg/SupervisorStatus.msg"
  "srv/MotorCommand.srv"
  "srv/RebootControllers.srv"
  "srv/RunScript.srv"
  "srv/SupervisorJob.srv"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
