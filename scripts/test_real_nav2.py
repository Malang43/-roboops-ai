#!/usr/bin/env python3

import math
import sys

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import (
    BasicNavigator,
    TaskResult,
)
from rclpy.duration import Duration


def create_pose(
    navigator: BasicNavigator,
    x: float,
    y: float,
    yaw: float,
) -> PoseStamped:
    pose = PoseStamped()

    pose.header.frame_id = "map"
    pose.header.stamp = (
        navigator.get_clock().now().to_msg()
    )

    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.position.z = 0.0

    pose.pose.orientation.z = math.sin(yaw / 2.0)
    pose.pose.orientation.w = math.cos(yaw / 2.0)

    return pose


def main() -> int:
    rclpy.init()

    navigator = BasicNavigator()

    try:
        # This matches the default TurtleBot3 spawn pose
        # used by the Humble Nav2 simulation.
        initial_pose = create_pose(
            navigator,
            x=-2.0,
            y=-0.5,
            yaw=0.0,
        )

        print("Setting initial robot pose...")
        navigator.setInitialPose(initial_pose)

        print("Waiting for Nav2 to become active...")
        navigator.waitUntilNav2Active()

        print("Nav2 is active.")

        # A real navigation destination inside the
        # standard TurtleBot3 simulation map.
        goal_pose = create_pose(
            navigator,
            x=-1.0,
            y=-0.5,
            yaw=0.0,
        )

        print(
            "Sending goal: "
            "x=-1.0, y=-0.5, yaw=0.0"
        )

        navigator.goToPose(goal_pose)

        feedback_count = 0

        while not navigator.isTaskComplete():
            feedback = navigator.getFeedback()
            feedback_count += 1

            if feedback and feedback_count % 10 == 0:
                navigation_time = Duration.from_msg(
                    feedback.navigation_time
                )

                if navigation_time > Duration(
                    seconds=180.0
                ):
                    print(
                        "Navigation exceeded 180 seconds. "
                        "Cancelling goal."
                    )
                    navigator.cancelTask()
                    break

                distance = getattr(
                    feedback,
                    "distance_remaining",
                    None,
                )

                if distance is not None:
                    print(
                        "Distance remaining: "
                        f"{distance:.2f} metres"
                    )
                else:
                    print("Robot is navigating...")

        result = navigator.getResult()

        if result == TaskResult.SUCCEEDED:
            print("REAL NAVIGATION RESULT: SUCCEEDED")
            return 0

        if result == TaskResult.CANCELED:
            print("REAL NAVIGATION RESULT: CANCELED")
            return 2

        if result == TaskResult.FAILED:
            print("REAL NAVIGATION RESULT: FAILED")
            return 1

        print("REAL NAVIGATION RESULT: UNKNOWN")
        return 1

    finally:
        navigator.destroyNode()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
