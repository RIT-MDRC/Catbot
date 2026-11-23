"""Orin service defaults; Pi configuration is owned by its separate launch."""

ORIN_DEFAULTS = {
    "jobs_json": "{}",
    "offline_jobs_json": "{}",
    "recording_directory": "~/.local/share/catbot/recordings",
    "operator": "",
    "pi_lease_timeout": 0.5,
    "action_timeout": 0.25,
    "simulation_mode": False,
    "scenario": "unspecified",
    "supervisor_run_id": "",
    "git_commit": "",
    "clock_tolerance": 0.02,
    "max_temperature_c": 80.0,
    "min_disk_free_bytes": 1073741824,
    "disk_path": "/",
    "compute_probe_timeout": 30.0,
    "resource_sys_root": "/sys",
    "resource_proc_root": "/proc",
}
