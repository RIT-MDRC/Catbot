# Catbot actuator tuning panel

Install `../ritmdrc.catbot-tuning-0.1.0.foxe` in Foxglove, then import the
adjacent `../main-dashboard.json` layout. Installing a local extension may
require a Foxglove developer seat. The panel needs a live ROS 2 Foxglove Bridge
connection with parameter access to `/foundation_node`.

Global gain uses `policy_gain_scale` (0.1–1.0). The three speed controls set
`abduction.speed_motor_turns_s`, `flexion.speed_motor_turns_s`, and
`knee.speed_motor_turns_s` (5–20 motor turns/second). Sliders and numeric inputs
require the ROS parameter to be available. Slider release or numeric entry
sends a request; if no matching ROS value arrives within three seconds the
control restores the last report and shows a warning. Mixed and out-of-range
values are labeled; a group value can become stale after per-axis changes. Reported ROS
parameter values are not motor firmware readback or an acknowledgement of motor
application. Gain updates require the configured gain baselines for all axes.

For development, run `npm ci` and `npm run package` in this directory. Reload
Foxglove after installing an updated extension.

The Actuator angles panel displays valid `/body/state/position` feedback. It
normalizes logical joint angles against the repository default limits: ±40°
for abduction/flexion and ±55° for knees. The limits are not fetched from the
active configuration; adapt the panel if that configuration differs. Values
are joint-position fractions, not policy actions. Missing or stale samples are
marked unavailable or stale.
