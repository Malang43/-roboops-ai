import asyncio
import json
import math
import threading
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any

import rclpy
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from geometry_msgs.msg import (
    PoseWithCovarianceStamped,
    Twist,
)
from nav_msgs.msg import (
    OccupancyGrid,
    Odometry,
    Path,
)
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


def quaternion_to_yaw(
    x: float,
    y: float,
    z: float,
    w: float,
) -> float:
    siny_cosp = 2.0 * (
        w * z + x * y
    )

    cosy_cosp = 1.0 - 2.0 * (
        y * y + z * z
    )

    return math.atan2(
        siny_cosp,
        cosy_cosp,
    )


class TelemetryStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()

        self.last_ros_update_wall: float | None = None
        self.last_clock_update_wall: float | None = None

        self.data: dict[str, Any] = {
            "connection": {
                "ros_online": False,
                "last_update_age_s": None,
            },
            "simulation": {
                "running": False,
                "sim_time_s": 0.0,
            },
            "robot": {
                "x": None,
                "y": None,
                "yaw_rad": None,
                "yaw_deg": None,
                "pose_source": None,
                "linear_speed_mps": 0.0,
                "angular_speed_rps": 0.0,
                "command_linear_mps": 0.0,
                "command_angular_rps": 0.0,
            },
            "sensors": {
                "laser_online": False,
                "minimum_obstacle_distance_m": None,
                "valid_laser_points": 0,
            },
            "navigation": {
                "status": "idle",
                "goal_x": None,
                "goal_y": None,
                "distance_remaining_m": None,
                "elapsed_s": None,
                "path": [],
                "path_point_count": 0,
            },
            "mission": {
                "mission_id": None,
                "plan_id": None,
                "status": "idle",
                "current_step": None,
                "total_steps": 0,
                "step_status": None,
                "progress_percent": 0,
                "action": None,
                "target": None,
                "description": None,
                "error": None,
            },
            "map": {
                "available": False,
                "frame_id": "map",
                "width": 0,
                "height": 0,
                "resolution": None,
                "origin_x": None,
                "origin_y": None,
            },
        }

    def update(
        self,
        section: str,
        values: dict[str, Any],
        *,
        mark_ros: bool = True,
    ) -> None:
        with self.lock:
            self.data[section].update(values)

            if mark_ros:
                self.last_ros_update_wall = (
                    time.monotonic()
                )

    def update_many(
        self,
        updates: dict[
            str,
            dict[str, Any],
        ],
    ) -> None:
        with self.lock:
            for section, values in updates.items():
                self.data[section].update(values)

            self.last_ros_update_wall = (
                time.monotonic()
            )

    def update_clock(
        self,
        sim_time_s: float,
    ) -> None:
        now = time.monotonic()

        with self.lock:
            self.data["simulation"][
                "sim_time_s"
            ] = round(sim_time_s, 3)

            self.last_ros_update_wall = now
            self.last_clock_update_wall = now

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()

        with self.lock:
            result = deepcopy(self.data)

            last_ros = self.last_ros_update_wall
            last_clock = self.last_clock_update_wall

        if last_ros is None:
            ros_age = None
            ros_online = False
        else:
            ros_age = max(
                0.0,
                now - last_ros,
            )
            ros_online = ros_age < 3.0

        simulation_running = (
            last_clock is not None
            and now - last_clock < 2.0
        )

        result["connection"][
            "ros_online"
        ] = ros_online

        result["connection"][
            "last_update_age_s"
        ] = (
            round(ros_age, 2)
            if ros_age is not None
            else None
        )

        result["simulation"][
            "running"
        ] = simulation_running

        result["generated_at"] = time.time()

        return result


STORE = TelemetryStore()


class RoboOpsTelemetryNode(Node):
    def __init__(self) -> None:
        super().__init__(
            "roboops_telemetry_bridge"
        )

        self.last_amcl_pose_wall = 0.0

        map_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=(
                ReliabilityPolicy.RELIABLE
            ),
            durability=(
                DurabilityPolicy.TRANSIENT_LOCAL
            ),
        )

        self.create_subscription(
            Odometry,
            "/odom",
            self.odom_callback,
            10,
        )

        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self.amcl_callback,
            10,
        )

        self.create_subscription(
            LaserScan,
            "/scan",
            self.scan_callback,
            qos_profile_sensor_data,
        )

        self.create_subscription(
            Twist,
            "/cmd_vel",
            self.cmd_vel_callback,
            10,
        )

        self.create_subscription(
            Path,
            "/plan",
            self.path_callback,
            10,
        )

        self.create_subscription(
            Clock,
            "/clock",
            self.clock_callback,
            qos_profile_sensor_data,
        )

        self.create_subscription(
            String,
            "/roboops/mission_status",
            self.mission_callback,
            10,
        )

        self.create_subscription(
            OccupancyGrid,
            "/map",
            self.map_callback,
            map_qos,
        )

        self.get_logger().info(
            "RoboOps telemetry bridge started"
        )

    def update_pose(
        self,
        position: Any,
        orientation: Any,
        source: str,
    ) -> None:
        yaw = quaternion_to_yaw(
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w,
        )

        STORE.update(
            "robot",
            {
                "x": round(
                    float(position.x),
                    4,
                ),
                "y": round(
                    float(position.y),
                    4,
                ),
                "yaw_rad": round(
                    yaw,
                    4,
                ),
                "yaw_deg": round(
                    math.degrees(yaw),
                    2,
                ),
                "pose_source": source,
            },
        )

    def odom_callback(
        self,
        message: Odometry,
    ) -> None:
        STORE.update(
            "robot",
            {
                "linear_speed_mps": round(
                    float(
                        message.twist.twist.linear.x
                    ),
                    4,
                ),
                "angular_speed_rps": round(
                    float(
                        message.twist.twist.angular.z
                    ),
                    4,
                ),
            },
        )

        # Prefer map-frame AMCL pose. Use odometry
        # as a fallback when AMCL has not updated.
        if (
            time.monotonic()
            - self.last_amcl_pose_wall
            > 3.0
        ):
            self.update_pose(
                message.pose.pose.position,
                message.pose.pose.orientation,
                "odom",
            )

    def amcl_callback(
        self,
        message: PoseWithCovarianceStamped,
    ) -> None:
        self.last_amcl_pose_wall = (
            time.monotonic()
        )

        self.update_pose(
            message.pose.pose.position,
            message.pose.pose.orientation,
            "amcl",
        )

    def scan_callback(
        self,
        message: LaserScan,
    ) -> None:
        valid_ranges = [
            float(distance)
            for distance in message.ranges
            if (
                math.isfinite(distance)
                and distance
                >= float(message.range_min)
                and distance
                <= float(message.range_max)
            )
        ]

        minimum_distance = (
            min(valid_ranges)
            if valid_ranges
            else None
        )

        STORE.update(
            "sensors",
            {
                "laser_online": True,
                "minimum_obstacle_distance_m": (
                    round(minimum_distance, 3)
                    if minimum_distance
                    is not None
                    else None
                ),
                "valid_laser_points": len(
                    valid_ranges
                ),
            },
        )

    def cmd_vel_callback(
        self,
        message: Twist,
    ) -> None:
        STORE.update(
            "robot",
            {
                "command_linear_mps": round(
                    float(message.linear.x),
                    4,
                ),
                "command_angular_rps": round(
                    float(message.angular.z),
                    4,
                ),
            },
        )

    def path_callback(
        self,
        message: Path,
    ) -> None:
        poses = message.poses

        # Keep the WebSocket payload compact.
        if len(poses) > 200:
            interval = max(
                1,
                len(poses) // 200,
            )
            selected = poses[::interval]
        else:
            selected = poses

        path_points = [
            {
                "x": round(
                    float(
                        pose.pose.position.x
                    ),
                    3,
                ),
                "y": round(
                    float(
                        pose.pose.position.y
                    ),
                    3,
                ),
            }
            for pose in selected
        ]

        STORE.update(
            "navigation",
            {
                "path": path_points,
                "path_point_count": len(poses),
            },
        )

    def clock_callback(
        self,
        message: Clock,
    ) -> None:
        sim_time_s = (
            float(message.clock.sec)
            + float(message.clock.nanosec)
            / 1_000_000_000
        )

        STORE.update_clock(sim_time_s)

    def map_callback(
        self,
        message: OccupancyGrid,
    ) -> None:
        STORE.update(
            "map",
            {
                "available": True,
                "frame_id": (
                    message.header.frame_id
                    or "map"
                ),
                "width": int(
                    message.info.width
                ),
                "height": int(
                    message.info.height
                ),
                "resolution": round(
                    float(
                        message.info.resolution
                    ),
                    4,
                ),
                "origin_x": round(
                    float(
                        message.info.origin.position.x
                    ),
                    3,
                ),
                "origin_y": round(
                    float(
                        message.info.origin.position.y
                    ),
                    3,
                ),
            },
        )

    def mission_callback(
        self,
        message: String,
    ) -> None:
        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError:
            self.get_logger().warning(
                "Ignored invalid mission status JSON"
            )
            return

        mission_values = {
            "mission_id": payload.get(
                "mission_id"
            ),
            "plan_id": payload.get(
                "plan_id"
            ),
            "status": payload.get(
                "status",
                "unknown",
            ),
            "current_step": payload.get(
                "current_step"
            ),
            "total_steps": payload.get(
                "total_steps",
                0,
            ),
            "step_status": payload.get(
                "step_status"
            ),
            "progress_percent": payload.get(
                "progress_percent",
                0,
            ),
            "action": payload.get(
                "action"
            ),
            "target": payload.get(
                "target"
            ),
            "description": payload.get(
                "description"
            ),
            "error": payload.get(
                "error"
            ),
        }

        navigation_values = {
            "status": payload.get(
                "navigation_status",
                payload.get(
                    "status",
                    "unknown",
                ),
            ),
            "goal_x": payload.get(
                "goal_x"
            ),
            "goal_y": payload.get(
                "goal_y"
            ),
            "distance_remaining_m": (
                payload.get(
                    "distance_remaining_m"
                )
            ),
            "elapsed_s": payload.get(
                "navigation_elapsed_s"
            ),
        }

        STORE.update_many(
            {
                "mission": mission_values,
                "navigation": (
                    navigation_values
                ),
            }
        )


ROS_NODE: RoboOpsTelemetryNode | None = None
ROS_EXECUTOR: SingleThreadedExecutor | None = None
ROS_THREAD: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ROS_NODE
    global ROS_EXECUTOR
    global ROS_THREAD

    rclpy.init(args=None)

    ROS_NODE = RoboOpsTelemetryNode()
    ROS_EXECUTOR = SingleThreadedExecutor()
    ROS_EXECUTOR.add_node(ROS_NODE)

    ROS_THREAD = threading.Thread(
        target=ROS_EXECUTOR.spin,
        name="roboops-telemetry-ros-spin",
        daemon=True,
    )

    ROS_THREAD.start()

    try:
        yield
    finally:
        if ROS_EXECUTOR is not None:
            ROS_EXECUTOR.shutdown()

        if ROS_NODE is not None:
            ROS_NODE.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

        if ROS_THREAD is not None:
            ROS_THREAD.join(timeout=2.0)


app = FastAPI(
    title="RoboOps Live Telemetry",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/api/telemetry/health")
def telemetry_health() -> dict[str, Any]:
    return {
        "service": "online",
        "telemetry": STORE.snapshot(),
    }


@app.websocket("/ws/telemetry")
async def telemetry_websocket(
    websocket: WebSocket,
) -> None:
    await websocket.accept()

    try:
        while True:
            await websocket.send_json(
                STORE.snapshot()
            )

            await asyncio.sleep(0.2)

    except WebSocketDisconnect:
        return
    except RuntimeError:
        return
