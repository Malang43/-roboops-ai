import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import rclpy
from fastapi import FastAPI
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    (
        "http://127.0.0.1:5678/webhook/"
        "roboops-mission-event"
    ),
)

N8N_AUTOMATION_ENABLED = os.getenv(
    "N8N_AUTOMATION_ENABLED",
    "true",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

WEBHOOK_TIMEOUT_SECONDS = 10
MAX_DELIVERY_ATTEMPTS = 3


class AutomationState:
    def __init__(self) -> None:
        self.lock = threading.Lock()

        self.data: dict[str, Any] = {
            "service": "starting",
            "enabled": N8N_AUTOMATION_ENABLED,
            "webhook_url": N8N_WEBHOOK_URL,
            "received_status_events": 0,
            "terminal_events_detected": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "last_mission_id": None,
            "last_event_status": None,
            "last_delivery_status": None,
            "last_http_status": None,
            "last_response": None,
            "last_error": None,
            "last_delivery_at": None,
        }

    def update(
        self,
        values: dict[str, Any],
    ) -> None:
        with self.lock:
            self.data.update(values)

    def increment(
        self,
        field: str,
    ) -> None:
        with self.lock:
            self.data[field] = (
                int(self.data.get(field, 0)) + 1
            )

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return deepcopy(self.data)


STATE = AutomationState()


class N8NAutomationBridge(Node):
    def __init__(self) -> None:
        super().__init__(
            "roboops_n8n_automation_bridge"
        )

        self.delivery_pool = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="n8n-delivery",
        )

        self.mission_context: dict[
            str,
            dict[str, Any],
        ] = {}

        self.delivered_events: set[
            tuple[str, str]
        ] = set()

        self.create_subscription(
            String,
            "/roboops/mission_status",
            self.status_callback,
            20,
        )

        STATE.update(
            {
                "service": "online",
            }
        )

        self.get_logger().info(
            "RoboOps n8n automation bridge started"
        )

        self.get_logger().info(
            f"n8n webhook: {N8N_WEBHOOK_URL}"
        )

    @staticmethod
    def merge_non_null(
        destination: dict[str, Any],
        source: dict[str, Any],
    ) -> None:
        for key, value in source.items():
            if value is not None:
                destination[key] = value

    def status_callback(
        self,
        message: String,
    ) -> None:
        STATE.increment(
            "received_status_events"
        )

        try:
            payload = json.loads(
                message.data
            )
        except json.JSONDecodeError:
            self.get_logger().warning(
                "Invalid mission-status JSON ignored"
            )
            return

        mission_id = str(
            payload.get("mission_id") or ""
        ).strip()

        if not mission_id:
            self.get_logger().warning(
                "Mission event has no mission_id"
            )
            return

        context = self.mission_context.setdefault(
            mission_id,
            {},
        )

        self.merge_non_null(
            context,
            payload,
        )

        status = str(
            payload.get("status") or ""
        ).strip().lower()

        STATE.update(
            {
                "last_mission_id": mission_id,
                "last_event_status": status,
            }
        )

        if status not in {
            "completed",
            "failed",
        }:
            return

        terminal_key = (
            mission_id,
            status,
        )

        if terminal_key in self.delivered_events:
            self.get_logger().info(
                "Duplicate terminal event ignored: "
                f"{mission_id} {status}"
            )
            return

        self.delivered_events.add(
            terminal_key
        )

        STATE.increment(
            "terminal_events_detected"
        )

        event = deepcopy(context)

        event.update(
            {
                "event_type": f"mission.{status}",
                "mission_id": mission_id,
                "status": status,
                "source": (
                    "roboops_ros2_automation_bridge"
                ),
                "automation_created_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }
        )

        if not N8N_AUTOMATION_ENABLED:
            self.get_logger().warning(
                "n8n automation is disabled"
            )
            return

        self.delivery_pool.submit(
            self.deliver_event,
            event,
        )

    def deliver_event(
        self,
        event: dict[str, Any],
    ) -> None:
        mission_id = str(
            event.get("mission_id")
        )

        request_body = json.dumps(
            event
        ).encode("utf-8")

        last_error: str | None = None

        for attempt in range(
            1,
            MAX_DELIVERY_ATTEMPTS + 1,
        ):
            request = urllib_request.Request(
                url=N8N_WEBHOOK_URL,
                data=request_body,
                method="POST",
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                    "Accept": "application/json",
                    "User-Agent": (
                        "RoboOps-Automation/1.0"
                    ),
                },
            )

            try:
                with urllib_request.urlopen(
                    request,
                    timeout=WEBHOOK_TIMEOUT_SECONDS,
                ) as response:
                    response_text = (
                        response.read().decode(
                            "utf-8"
                        )
                    )

                    http_status = response.status

                STATE.increment(
                    "successful_deliveries"
                )

                STATE.update(
                    {
                        "last_delivery_status": (
                            "delivered"
                        ),
                        "last_http_status": (
                            http_status
                        ),
                        "last_response": (
                            response_text[:2000]
                        ),
                        "last_error": None,
                        "last_delivery_at": (
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        ),
                    }
                )

                self.get_logger().info(
                    "Mission event delivered to n8n: "
                    f"{mission_id} HTTP {http_status}"
                )

                return

            except urllib_error.HTTPError as error:
                try:
                    response_text = (
                        error.read().decode(
                            "utf-8"
                        )
                    )
                except Exception:
                    response_text = str(error)

                last_error = (
                    f"HTTP {error.code}: "
                    f"{response_text}"
                )

            except urllib_error.URLError as error:
                last_error = (
                    "Connection error: "
                    f"{error.reason}"
                )

            except TimeoutError:
                last_error = (
                    "n8n request timed out"
                )

            except Exception as error:
                last_error = str(error)

            self.get_logger().warning(
                f"Delivery attempt {attempt}/"
                f"{MAX_DELIVERY_ATTEMPTS} "
                f"failed: {last_error}"
            )

            if attempt < MAX_DELIVERY_ATTEMPTS:
                time.sleep(attempt * 2)

        STATE.increment(
            "failed_deliveries"
        )

        STATE.update(
            {
                "last_delivery_status": "failed",
                "last_error": last_error,
                "last_delivery_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }
        )

        self.get_logger().error(
            "Mission event could not be "
            f"delivered to n8n: {mission_id}"
        )

    def destroy_node(self) -> bool:
        self.delivery_pool.shutdown(
            wait=False,
            cancel_futures=True,
        )

        return super().destroy_node()


ROS_NODE: N8NAutomationBridge | None = None
ROS_EXECUTOR: SingleThreadedExecutor | None = None
ROS_THREAD: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ROS_NODE
    global ROS_EXECUTOR
    global ROS_THREAD

    rclpy.init(args=None)

    ROS_NODE = N8NAutomationBridge()

    ROS_EXECUTOR = SingleThreadedExecutor()
    ROS_EXECUTOR.add_node(ROS_NODE)

    ROS_THREAD = threading.Thread(
        target=ROS_EXECUTOR.spin,
        name="roboops-n8n-ros-spin",
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
    title="RoboOps n8n Automation Bridge",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/api/automation/health")
def automation_health() -> dict[str, Any]:
    return STATE.snapshot()
