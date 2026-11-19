# Reports only. The RPi Supervisor owns the link verdict.
builtin_interfaces/Time stamp
string session
uint64 sequence
uint64 action_sequence
uint64 probe_id
bool policy_active
bool degraded
string reason
# Readiness is distinct from process existence; verified is runtime SHA verification.
bool policy_ready
bool policy_verified
string bundle_id
string load_error
bool preflight_passed
string preflight_reason
