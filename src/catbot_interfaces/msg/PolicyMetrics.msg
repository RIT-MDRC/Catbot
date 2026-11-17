# Five-second policy reporting window, stamped at publication.
builtin_interfaces/Time stamp
string device
float64 window_seconds
float64 control_interval_ms
float64 published_hz
uint64 sample_count
# Timing percentiles cover accepted actions only; NaN when sample_count is zero.
float64 inference_p50_ms
float64 inference_p95_ms
float64 inference_p99_ms
float64 round_trip_p50_ms
float64 round_trip_p95_ms
float64 round_trip_p99_ms
# Age from local feedback receipt to action publication, excluding inbound transit.
float64 feedback_age_p50_ms
float64 feedback_age_p95_ms
float64 feedback_age_p99_ms
uint64 missed_timer_intervals
uint64 busy_ticks
uint64 discarded_results
# CPU percentages relative to one core; values may exceed 100.
float64 adapter_cpu_percent_one_core
uint64 adapter_peak_rss_kib
# Worker measurements are NaN until available. RSS is a lifetime high-water mark.
float64 worker_cpu_percent_one_core
float64 worker_peak_rss_kib
