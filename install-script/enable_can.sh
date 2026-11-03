#!/bin/bash

set -euo pipefail

if ! ip link show can0 >/dev/null 2>&1; then
  echo "can0 was not found. Check the Raspberry Pi SPI CAN overlay and reboot." >&2
  exit 1
fi

sudo ip link set can0 down 2>/dev/null || true
sudo ip link set can0 type can bitrate 250000 restart-ms 100
sudo ip link set can0 up
ip -details link show can0
