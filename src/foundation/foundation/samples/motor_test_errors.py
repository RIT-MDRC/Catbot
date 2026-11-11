"""Error and safety-warning text for the interactive motor-test sample."""


class MotorTestErrors:
    """Keep message templates separate from motor-control decisions and I/O."""

    INVALID_MOTOR_SELECTION = "Invalid command: supply valid motor names or axis IDs (comma-separated for multiple motors), or start motor-test with --motor."
    POSITIVE_SPEED_REQUIRED = "speed must be finite and greater than zero"
    POSITIVE_ACCELERATION_REQUIRED = "acceleration must be finite and greater than zero"
    FINITE_ANGLE_REQUIRED = "angle must be finite"
    CURRENT_POSITION_REQUIRED = "relative motion requires a current position"
    UNKNOWN_POSITION_COMMAND = 'unknown position command "{command}"'
    BUS_ERRORS = "ODrive error(s) detected on the CAN bus:"
    AMBIGUOUS_AXIS = 'Axis ID "{selector}" is ambiguous: {names}.'
    UNKNOWN_MOTOR = 'Unknown motor name or axis ID "{selector}".'
    NO_HEARTBEAT = "No heartbeat received from {name}."
    HEARTBEAT_HELP = "Confirm can0 is up, the 250000 bitrate matches the ODrive, and the configured axis ID is correct."
    EMPTY_COMMAND = (
        "Invalid command. Use mp or mr with a finite angle, a shortcut command, or q."
    )
    UNKNOWN_COMMAND = "Invalid command. Use mp <angle> [motor] for an absolute position or mr <angle> [motor] for relative motion."
    INVALID_POSITION_SELECTION = "Invalid command: supply valid motor names or axis IDs after '{position_command} <angle>' (comma-separated for multiple motors), or start motor-test with --motor."
    NO_ENCODER_POSITION = "No encoder position received from {name}."
    NO_ENCODER_SPEED = "No encoder speed received from {name}."
    POSITION_READ_FAILED = "{name}: joint angle unavailable ({error}); raw position: {turns:.4f} motor turns."
    SPEED_READ_FAILED = "{name}: joint speed unavailable ({error}); raw speed: {turns:.4f} motor turns/second."
    FAULT_BEFORE_ARM = "Clear the ODrive error on {name} before arming."
    NO_HOLD_POSITION = "No encoder position received from {name}; refusing to arm without a safe initial hold position."
    ARM_WARNING = (
        "WARNING: arming {name} enables motor torque; keep the mechanism clear."
    )
    TRAJECTORY_FAILED = "Failed to configure position trajectory for {name}."
    HOLD_FAILED = "Failed to send the initial position hold to {name}."
    ARM_REQUEST_FAILED = "Failed to send the closed-loop request to {name}."
    ARM_NOT_CONFIRMED = "{name} did not confirm that it is armed."
    DISARM_REQUEST_FAILED = "Failed to send the disarm command to {name}."
    DISARM_NOT_CONFIRMED = "{name} did not confirm that it is disarmed."
    CLEAR_FAILED = "Failed to clear errors for {name}."
    MOVEMENT_WARNING = (
        "WARNING: {action_name} moves the motor; keep the mechanism clear."
    )
    STATE_REQUEST_FAILED = "Failed to send {action_name} to {name}."
    INVALID_SPEED = (
        "Invalid speed. Use: speed <positive degrees/second> [motor[,motor...]]."
    )
    SPEED_FAILED = "Failed to set speed for {name}."
    INVALID_ACCELERATION = "Invalid acceleration. Use: accel <positive motor turns/second²> [motor[,motor...]]."
    ACCELERATION_FAILED = "Failed to set acceleration/deceleration for {name}."
    INVALID_ANGLE = "Invalid command. Use {command} <finite angle> [motor[,motor...]]."
    FAULT_BEFORE_MOTION = "Clear the error on {name} before commanding motion."
    DISARMED = "{name} is disarmed; run 'arm {name}'."
    NO_RELATIVE_POSITION = "No encoder position received from {name}; relative motion requires a current position."
    TARGET_REJECTED = "Command rejected for {name}: {error}."
    TARGET_FAILED = "Command rejected for {name}; check its position bounds."
    START_FAILED = "Unable to start motor test: {error}"
    INTERFACE_FAILED = "Motor-test interface failed: {error}"
