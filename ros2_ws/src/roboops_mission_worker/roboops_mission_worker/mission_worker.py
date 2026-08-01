import json
import math
import time
from datetime import datetime, timezone
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import (
    BasicNavigator,
    TaskResult,
)
from rclpy.duration import Duration
from rclpy.node import Node
from std_msgs.msg import String


NAMED_LOCATIONS: dict[str, dict[str, float]] = {
    "home": {
        "x": -2.0,
        "y": -0.5,
        "yaw": 0.0,
    },
    "room_a": {
        "x": -1.0,
        "y": -0.5,
        "yaw": 0.0,
    },
}


NAVIGATION_TIMEOUT_SECONDS = 180.0

VISION_BASE_URL = "http://127.0.0.1:8002"
VISION_TIMEOUT_SECONDS = 8.0



class MissionExecutionError(RuntimeError):
    pass


class MissionWorker(Node):
    def __init__(self) -> None:
        super().__init__("roboops_mission_worker")

        self.status_publisher = self.create_publisher(
            String,
            "/roboops/mission_status",
            10,
        )

        self.create_subscription(
            String,
            "/roboops/mission_command",
            self.mission_callback,
            10,
        )

        self.navigator = BasicNavigator()

        self.get_logger().info(
            "Initializing Nav2 connection..."
        )

        self.initialize_navigation()

        self.get_logger().info(
            "Mission worker is ready for real Nav2 missions"
        )

    def create_pose(
        self,
        x: float,
        y: float,
        yaw: float,
    ) -> PoseStamped:
        pose = PoseStamped()

        pose.header.frame_id = "map"
        pose.header.stamp = (
            self.navigator.get_clock().now().to_msg()
        )

        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0

        pose.pose.orientation.z = math.sin(
            yaw / 2.0
        )
        pose.pose.orientation.w = math.cos(
            yaw / 2.0
        )

        return pose

    def initialize_navigation(self) -> None:
        home = NAMED_LOCATIONS["home"]

        initial_pose = self.create_pose(
            x=home["x"],
            y=home["y"],
            yaw=home["yaw"],
        )

        self.get_logger().info(
            "Publishing initial robot pose"
        )

        self.navigator.setInitialPose(
            initial_pose
        )

        self.get_logger().info(
            "Waiting for Nav2 to become active"
        )

        self.navigator.waitUntilNav2Active()

        self.get_logger().info(
            "Nav2 is active and ready"
        )

    def publish_status(
        self,
        mission: dict[str, Any],
        status: str,
        step: dict[str, Any] | None = None,
        step_status: str | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        steps = mission.get("steps") or []
        total_steps = len(steps)

        current_step = (
            step.get("step_number")
            if step is not None
            else None
        )

        completed_steps = 0

        if current_step is not None:
            completed_steps = current_step - 1

            if step_status == "completed":
                completed_steps = current_step

        if status == "completed":
            completed_steps = total_steps

        progress_percent = (
            int(completed_steps / total_steps * 100)
            if total_steps
            else 0
        )

        event: dict[str, Any] = {
            "mission_id": mission.get("mission_id"),
            "plan_id": mission.get("plan_id"),
            "status": status,
            "worker": self.get_name(),
            "event_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "current_step": current_step,
            "total_steps": total_steps,
            "step_status": step_status,
            "progress_percent": progress_percent,
            "action": (
                step.get("action")
                if step is not None
                else mission.get("action")
            ),
            "target": (
                step.get("target")
                if step is not None
                else mission.get("target")
            ),
            "description": (
                step.get("description")
                if step is not None
                else None
            ),
        }

        if error is not None:
            event["error"] = error

        if extra:
            event.update(extra)

        message = String()
        message.data = json.dumps(event)

        self.status_publisher.publish(message)

        self.get_logger().info(
            f"Status={status} "
            f"step={current_step} "
            f"step_status={step_status} "
            f"progress={progress_percent}%"
        )

    def resolve_location(
        self,
        target: str | None,
    ) -> dict[str, float]:
        normalized_target = (
            target.strip().lower()
            if target
            else ""
        )

        if normalized_target not in NAMED_LOCATIONS:
            supported = ", ".join(
                sorted(NAMED_LOCATIONS)
            )

            raise MissionExecutionError(
                f"Unknown navigation target "
                f"'{target}'. Supported locations: "
                f"{supported}"
            )

        return NAMED_LOCATIONS[
            normalized_target
        ]

    def navigate_to(
        self,
        mission: dict[str, Any],
        step: dict[str, Any],
        target: str,
    ) -> None:
        location = self.resolve_location(target)

        goal_pose = self.create_pose(
            x=location["x"],
            y=location["y"],
            yaw=location["yaw"],
        )

        self.get_logger().info(
            f"Sending real Nav2 goal: "
            f"{target} "
            f"x={location['x']}, "
            f"y={location['y']}"
        )

        self.navigator.clearAllCostmaps()
        self.navigator.goToPose(goal_pose)

        feedback_counter = 0

        while not self.navigator.isTaskComplete():
            feedback = self.navigator.getFeedback()
            feedback_counter += 1

            if feedback is None:
                continue

            navigation_time = Duration.from_msg(
                feedback.navigation_time
            )

            if navigation_time > Duration(
                seconds=NAVIGATION_TIMEOUT_SECONDS
            ):
                self.navigator.cancelTask()

                raise MissionExecutionError(
                    "Navigation exceeded "
                    f"{NAVIGATION_TIMEOUT_SECONDS:.0f} "
                    "seconds"
                )

            if feedback_counter % 10 != 0:
                continue

            distance_remaining = float(
                getattr(
                    feedback,
                    "distance_remaining",
                    0.0,
                )
            )

            elapsed_seconds = (
                navigation_time.nanoseconds
                / 1_000_000_000
            )

            self.publish_status(
                mission=mission,
                status="running",
                step=step,
                step_status="running",
                extra={
                    "navigation_status": (
                        "moving"
                    ),
                    "distance_remaining_m": round(
                        distance_remaining,
                        3,
                    ),
                    "navigation_elapsed_s": round(
                        elapsed_seconds,
                        1,
                    ),
                    "goal_x": location["x"],
                    "goal_y": location["y"],
                },
            )

        result = self.navigator.getResult()

        if result == TaskResult.SUCCEEDED:
            self.get_logger().info(
                f"Nav2 goal succeeded: {target}"
            )
            return

        if result == TaskResult.CANCELED:
            raise MissionExecutionError(
                f"Navigation to {target} "
                "was cancelled"
            )

        if result == TaskResult.FAILED:
            raise MissionExecutionError(
                f"Navigation to {target} failed"
            )

        raise MissionExecutionError(
            f"Navigation to {target} "
            "returned an unknown result"
        )

    def execute_navigation_step(
        self,
        mission: dict[str, Any],
        step: dict[str, Any],
    ) -> None:
        action = (
            str(step.get("action") or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        target = step.get("target")

        if action == "return_home":
            target = "home"

        elif action == "navigate" and not target:
            description = str(
                step.get("description") or ""
            ).lower()

            if any(
                phrase in description
                for phrase in [
                    "home",
                    "base",
                    "starting point",
                    "start position",
                ]
            ):
                target = "home"
            else:
                # Current demonstration world has one
                # supported destination: Room A.
                target = "room_a"

            self.get_logger().warning(
                "Navigate step had no target. "
                f"Using inferred target: {target}"
            )

        if not target:
            raise MissionExecutionError(
                f"The {action} step has no target"
            )

        self.navigate_to(
            mission=mission,
            step=step,
            target=str(target),
        )

    def request_vision(
        self,
        endpoint: str,
        method: str = "GET",
    ) -> dict[str, Any]:
        url = (
            VISION_BASE_URL
            + endpoint
        )

        request_data = (
            b""
            if method == "POST"
            else None
        )

        request = urllib_request.Request(
            url=url,
            data=request_data,
            method=method,
            headers={
                "Accept": "application/json",
            },
        )

        try:
            with urllib_request.urlopen(
                request,
                timeout=VISION_TIMEOUT_SECONDS,
            ) as response:
                body = response.read().decode(
                    "utf-8"
                )

        except urllib_error.HTTPError as error:
            try:
                detail = error.read().decode(
                    "utf-8"
                )
            except Exception:
                detail = str(error)

            raise MissionExecutionError(
                "Vision service returned "
                f"HTTP {error.code}: {detail}"
            ) from error

        except urllib_error.URLError as error:
            raise MissionExecutionError(
                "Vision service is unavailable at "
                f"{VISION_BASE_URL}: {error.reason}"
            ) from error

        except TimeoutError as error:
            raise MissionExecutionError(
                "Vision service request timed out"
            ) from error

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise MissionExecutionError(
                "Vision service returned invalid JSON"
            ) from error

        if not isinstance(payload, dict):
            raise MissionExecutionError(
                "Vision service returned an "
                "unexpected response"
            )

        return payload

    def execute_detect_object(
        self,
        mission: dict[str, Any],
        step: dict[str, Any],
    ) -> None:
        payload = self.request_vision(
            "/api/vision/latest"
        )

        if not payload.get("camera_online"):
            raise MissionExecutionError(
                "The Gazebo camera is offline"
            )

        detections = (
            payload.get("detections")
            or []
        )

        target = (
            str(
                step.get("target")
                or "any"
            )
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        target_aliases = {
            "green": "green_structure",
            "green_object": "green_structure",
            "structure": "green_structure",
            "red": "red_marker",
            "marker": "red_marker",
            "red_object": "red_marker",
        }

        target = target_aliases.get(
            target,
            target,
        )

        generic_targets = {
            "",
            "any",
            "object",
            "objects",
            "any_object",
            "visible_object",
            "visible_objects",
        }

        if target in generic_targets:
            matching = detections
        else:
            matching = [
                detection
                for detection in detections
                if (
                    str(
                        detection.get("label")
                        or ""
                    ).lower()
                    == target
                )
            ]

        detection_found = bool(
            matching
        )

        labels = [
            str(
                detection.get("label")
                or "unknown"
            )
            for detection in detections
        ]

        if detection_found:
            self.get_logger().info(
                "Vision detection succeeded: "
                f"{len(matching)} matching object(s)"
            )
        else:
            self.get_logger().warning(
                "Vision inspection completed, but "
                f"target '{target}' was not detected"
            )

        self.publish_status(
            mission=mission,
            status="running",
            step=step,
            step_status="running",
            extra={
                "execution_mode": "real_vision",
                "vision_action": "detect_object",
                "camera_online": True,
                "detection_found": detection_found,
                "detection_target": target,
                "detection_count": len(
                    detections
                ),
                "detected_labels": labels,
                "detections": detections,
            },
        )

    def execute_capture_image(
        self,
        mission: dict[str, Any],
        step: dict[str, Any],
    ) -> None:
        health = self.request_vision(
            "/api/vision/latest"
        )

        if not health.get("camera_online"):
            raise MissionExecutionError(
                "Cannot capture because the "
                "Gazebo camera is offline"
            )

        result = self.request_vision(
            "/api/vision/capture",
            method="POST",
        )

        capture_path = result.get(
            "path"
        )

        if not capture_path:
            raise MissionExecutionError(
                "Vision service did not return "
                "a capture path"
            )

        self.get_logger().info(
            "Inspection image captured: "
            f"{capture_path}"
        )

        self.publish_status(
            mission=mission,
            status="running",
            step=step,
            step_status="running",
            extra={
                "execution_mode": "real_vision",
                "vision_action": "capture_image",
                "capture_status": "saved",
                "capture_path": capture_path,
                "capture_detections": (
                    result.get("detections")
                    or []
                ),
            },
        )

    def execute_software_step(
        self,
        mission: dict[str, Any],
        step: dict[str, Any],
    ) -> None:
        action = (
            str(step.get("action") or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        if action == "detect_object":
            self.execute_detect_object(
                mission,
                step,
            )
            return

        if action == "capture_image":
            self.execute_capture_image(
                mission,
                step,
            )
            return

        if action == "inspect_path":
            self.get_logger().info(
                "Executing path inspection step"
            )

            self.publish_status(
                mission=mission,
                status="running",
                step=step,
                step_status="running",
                extra={
                    "execution_mode": (
                        "software_placeholder"
                    ),
                },
            )

            time.sleep(1)
            return

        raise MissionExecutionError(
            f"Unsupported software action: {action}"
        )

    def execute_step(
        self,
        mission: dict[str, Any],
        step: dict[str, Any],
    ) -> None:
        action = (
            str(step.get("action") or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        step["action"] = action

        self.publish_status(
            mission=mission,
            status="running",
            step=step,
            step_status="running",
        )

        if action in {
            "navigate",
            "return_home",
        }:
            self.execute_navigation_step(
                mission,
                step,
            )
        elif action in {
            "inspect_path",
            "detect_object",
            "capture_image",
        }:
            self.execute_software_step(
                mission,
                step,
            )
        else:
            raise MissionExecutionError(
                f"Unsupported mission action: "
                f"{action}"
            )

        self.publish_status(
            mission=mission,
            status="running",
            step=step,
            step_status="completed",
        )

    def execute_plan(
        self,
        mission: dict[str, Any],
    ) -> None:
        steps = mission.get("steps") or []

        # Support manual dashboard missions that contain
        # action and target at the top level instead of
        # an AI-generated steps array.
        if not steps:
            action = str(
                mission.get("action") or ""
            ).strip().lower()

            action = (
                action
                .replace("-", "_")
                .replace(" ", "_")
            )

            target = mission.get("target")

            if not action:
                raise MissionExecutionError(
                    "Mission contains no action"
                )

            steps = [
                {
                    "step_number": 1,
                    "action": action,
                    "target": target,
                    "description": (
                        f"Manual dashboard mission: "
                        f"{action} to {target}"
                    ),
                }
            ]

            mission["steps"] = steps

            self.get_logger().info(
                "Converted manual mission into "
                "a one-step execution plan"
            )

        self.publish_status(
            mission=mission,
            status="received",
        )

        for step in steps:
            self.get_logger().info(
                f"Executing step "
                f"{step.get('step_number')}: "
                f"{step.get('action')} → "
                f"{step.get('target')}"
            )

            self.execute_step(
                mission,
                step,
            )

        self.publish_status(
            mission=mission,
            status="completed",
            extra={
                "navigation_status": (
                    "mission_complete"
                ),
            },
        )

    def mission_callback(
        self,
        message: String,
    ) -> None:
        mission: dict[str, Any] = {}

        try:
            mission = json.loads(message.data)

            self.get_logger().info(
                "Received mission: "
                f"{mission.get('mission_id')}"
            )

            self.execute_plan(mission)

        except json.JSONDecodeError:
            self.get_logger().error(
                "Received invalid JSON"
            )

            self.publish_status(
                mission=mission,
                status="failed",
                error="Invalid JSON command",
            )

        except Exception as error:
            self.get_logger().error(
                f"Mission failed: {error}"
            )

            self.navigator.cancelTask()

            self.publish_status(
                mission=mission,
                status="failed",
                error=str(error),
            )

    def destroy_node(self) -> bool:
        self.navigator.destroyNode()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)

    node = MissionWorker()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
