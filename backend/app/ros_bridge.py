import json
import threading
from collections.abc import Callable
from typing import Any

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


StatusHandler = Callable[[dict[str, Any]], None]


class RosBridge:
    def __init__(
        self,
        status_handler: StatusHandler | None = None,
    ) -> None:
        self.node: Node | None = None
        self.executor: SingleThreadedExecutor | None = None
        self.thread: threading.Thread | None = None
        self.publisher = None
        self.latest_status: dict[str, Any] | None = None
        self.running = False

        self.status_handler = status_handler
        self._lock = threading.Lock()

    def start(self) -> None:
        if self.running:
            return

        if not rclpy.ok():
            rclpy.init(args=None)

        self.node = Node("roboops_api_bridge")

        self.publisher = self.node.create_publisher(
            String,
            "/roboops/mission_command",
            10,
        )

        self.node.create_subscription(
            String,
            "/roboops/mission_status",
            self._status_callback,
            10,
        )

        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.thread = threading.Thread(
            target=self.executor.spin,
            daemon=True,
        )

        self.thread.start()
        self.running = True

        self.node.get_logger().info(
            "RoboOps API ROS bridge started"
        )

    def _status_callback(self, message: String) -> None:
        try:
            status = json.loads(message.data)
        except json.JSONDecodeError:
            status = {
                "status": "invalid_ros_message",
                "raw_data": message.data,
            }

        with self._lock:
            self.latest_status = status

        if self.status_handler is not None:
            try:
                self.status_handler(status)
            except Exception as error:
                if self.node is not None:
                    self.node.get_logger().error(
                        "Status persistence failed: "
                        f"{error}"
                    )

    def publish_mission(
        self,
        mission: dict[str, Any],
    ) -> None:
        if not self.running or self.publisher is None:
            raise RuntimeError(
                "ROS2 bridge is not running"
            )

        message = String()
        message.data = json.dumps(mission)

        self.publisher.publish(message)

    def get_latest_status(
        self,
    ) -> dict[str, Any] | None:
        with self._lock:
            return self.latest_status

    def stop(self) -> None:
        self.running = False

        if self.executor is not None:
            self.executor.shutdown()

        if self.node is not None:
            self.node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()
