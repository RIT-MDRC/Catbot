# Complete sensor-dependent policy snapshot, in simulation coordinates.
# stamp is informational; the policy node measures freshness from local receipt.
builtin_interfaces/Time stamp
# Height in meters, followed by orientation (w, x, y, z).
float64[5] base_height_quaternion
# Horizontal heading frame, +X forward, +Y left, +Z up; meters/second.
float64[3] heading_linear_velocity
# Body-local angular velocity in radians/second.
float64[3] base_angular_velocity
# FL, FR, RL, RR; abduction, flexion, knee within each leg.
# Model coordinates, radians and radians/second (not hardware logical degrees).
float64[12] joint_positions
float64[12] joint_velocities
# Feet in FL, FR, RL, RR order. Provider maintains contact/episode history.
float64[4] normalized_air_time
bool[4] previous_contact
bool[4] has_stance
# Provider maintains the training motion-budget window and normalized travel.
float64[12] motion_travel
float64 motion_progress
