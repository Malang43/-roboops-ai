#!/usr/bin/env bash

set -o pipefail

PASS_COUNT=0
FAIL_COUNT=0


pass() {
  echo "[PASS] $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}


fail() {
  echo "[FAIL] $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}


check_unit() {
  local unit="$1"

  if systemctl is-active \
    --quiet "$unit"; then
    pass "systemd: $unit"
  else
    fail "systemd: $unit"
  fi
}


check_container() {
  local container="$1"

  if docker inspect \
    -f '{{.State.Running}}' \
    "$container" \
    2>/dev/null |
    grep -qx "true"; then

    pass "Docker: $container"
  else
    fail "Docker: $container"
  fi
}


check_http() {
  local name="$1"
  local url="$2"

  if curl \
    -fsSL \
    --max-time 8 \
    "$url" \
    >/dev/null 2>&1; then

    pass "HTTP: $name"
  else
    fail "HTTP: $name"
  fi
}


echo
echo "====================================="
echo " RoboOps AI System Health Check"
echo "====================================="
echo


echo "--- systemd services ---"

for unit in \
  roboops-infrastructure.service \
  roboops-simulation.service \
  roboops-mission-worker.service \
  roboops-backend.service \
  roboops-telemetry.service \
  roboops-vision.service \
  roboops-automation.service \
  roboops-reports.service \
  roboops-frontend.service
do
  check_unit "$unit"
done


echo
echo "--- Docker infrastructure ---"

check_container "roboops-postgres"
check_container "roboops-redis"
check_container "roboops-n8n"


echo
echo "--- HTTP services ---"

check_http \
  "React dashboard" \
  "http://127.0.0.1:5173/"

check_http \
  "FastAPI backend" \
  "http://127.0.0.1:8000/docs"

check_http \
  "Telemetry service" \
  "http://127.0.0.1:8001/api/telemetry/health"

check_http \
  "Vision service" \
  "http://127.0.0.1:8002/api/vision/health"

check_http \
  "Automation service" \
  "http://127.0.0.1:8003/api/automation/health"

check_http \
  "Report service" \
  "http://127.0.0.1:8004/api/reports/health"

check_http \
  "n8n" \
  "http://127.0.0.1:5678/"


echo
echo "--- ROS2 and Nav2 ---"

if timeout 10 bash -lc '
  source /opt/ros/humble/setup.bash
  source /srv/roboops-ai/ros2_ws/install/setup.bash

  ros2 action list |
    grep -qx "/navigate_to_pose"
'; then
  pass "Nav2 action: /navigate_to_pose"
else
  fail "Nav2 action: /navigate_to_pose"
fi


if timeout 10 bash -lc '
  source /opt/ros/humble/setup.bash
  source /srv/roboops-ai/ros2_ws/install/setup.bash

  ros2 topic echo /odom \
    --once \
    >/dev/null
'; then
  pass "ROS2 topic: /odom"
else
  fail "ROS2 topic: /odom"
fi


if timeout 10 bash -lc '
  source /opt/ros/humble/setup.bash
  source /srv/roboops-ai/ros2_ws/install/setup.bash

  ros2 topic echo /scan \
    --once \
    >/dev/null
'; then
  pass "ROS2 topic: /scan"
else
  fail "ROS2 topic: /scan"
fi


if timeout 10 bash -lc '
  source /opt/ros/humble/setup.bash
  source /srv/roboops-ai/ros2_ws/install/setup.bash

  ros2 topic echo \
    /intel_realsense_r200_depth/image_raw \
    --once \
    --field header \
    >/dev/null
'; then
  pass "ROS2 RGB camera"
else
  fail "ROS2 RGB camera"
fi


echo
echo "====================================="
echo " Passed: $PASS_COUNT"
echo " Failed: $FAIL_COUNT"
echo "====================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi

exit 0
