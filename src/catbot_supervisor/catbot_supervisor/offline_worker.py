"""Linux resource envelope for allowlisted offline jobs, applied before exec."""

import argparse
import os
import resource


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--cpu-seconds", type=int, default=600)
    parser.add_argument("--memory-mib", type=int, default=2048)
    parser.add_argument("--cpu", type=int, default=-1)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.cpu_seconds < 1 or args.memory_mib < 1 or not command:
        parser.error("positive limits and a command are required")
    os.nice(15)
    if args.cpu >= 0:
        os.sched_setaffinity(0, {args.cpu})
    memory = args.memory_mib * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (args.cpu_seconds, args.cpu_seconds))
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
