#!/usr/bin/env bash

set -e

PROJECT_ROOT="/srv/roboops-ai"
UNIT_SOURCE="$PROJECT_ROOT/deployment/systemd"
UNIT_DESTINATION="/etc/systemd/system"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo."
  exit 1
fi

cp "$UNIT_SOURCE"/roboops-*.service \
   "$UNIT_SOURCE"/roboops.target \
   "$UNIT_DESTINATION"/

systemctl daemon-reload
systemctl enable roboops.target

echo
echo "RoboOps systemd services installed."
echo
echo "Start:"
echo "  sudo systemctl start roboops.target"
echo
echo "Check:"
echo "  $PROJECT_ROOT/scripts/roboops-health.sh"
