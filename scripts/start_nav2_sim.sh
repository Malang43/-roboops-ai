#!/usr/bin/env bash

set -eo pipefail

source /opt/ros/humble/setup.bash

if [ -f /srv/roboops-ai/ros2_ws/install/setup.bash ]; then
  source /srv/roboops-ai/ros2_ws/install/setup.bash
fi

export TURTLEBOT3_MODEL=waffle

export GAZEBO_MODEL_PATH="${GAZEBO_MODEL_PATH:-}:/opt/ros/humble/share/turtlebot3_gazebo/models"

# Force software OpenGL rendering inside the
# virtual X display. No physical display or
# remote Gazebo window is required.
export LIBGL_ALWAYS_SOFTWARE=1
export QT_X11_NO_MITSHM=1

exec xvfb-run \
  -a \
  -s "-screen 0 1280x720x24 -ac" \
  ros2 launch nav2_bringup tb3_simulation_launch.py \
    headless:=True \
    use_rviz:=False \
    use_composition:=False \
    autostart:=True
