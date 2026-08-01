import json
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String


CAPTURE_FOLDER = Path(
    "/srv/roboops-ai/data/captures"
)

CAPTURE_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)


class VisionState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.condition = threading.Condition(
            self.lock
        )

        self.latest_jpeg: bytes | None = None
        self.camera_topic: str | None = None
        self.camera_format: str | None = None
        self.last_frame_wall: float | None = None
        self.frame_count = 0
        self.processing_fps = 0.0
        self.last_processing_wall: float | None = None

        self.frame_width = 0
        self.frame_height = 0

        self.detections: list[
            dict[str, Any]
        ] = []

        self.last_capture_path: str | None = None

        self.create_placeholder()

    def create_placeholder(self) -> None:
        frame = np.zeros(
            (480, 720, 3),
            dtype=np.uint8,
        )

        frame[:] = (18, 24, 39)

        cv2.putText(
            frame,
            "RoboOps Vision",
            (210, 210),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (220, 225, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            "Waiting for ROS2 camera...",
            (175, 260),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (145, 155, 185),
            2,
            cv2.LINE_AA,
        )

        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [
                int(
                    cv2.IMWRITE_JPEG_QUALITY
                ),
                85,
            ],
        )

        if success:
            self.latest_jpeg = (
                encoded.tobytes()
            )

    def set_camera(
        self,
        topic: str,
        camera_format: str,
    ) -> None:
        with self.lock:
            self.camera_topic = topic
            self.camera_format = camera_format

    def update_frame(
        self,
        jpeg: bytes,
        width: int,
        height: int,
        detections: list[
            dict[str, Any]
        ],
    ) -> None:
        now = time.monotonic()

        with self.condition:
            if (
                self.last_processing_wall
                is not None
            ):
                elapsed = (
                    now
                    - self.last_processing_wall
                )

                if elapsed > 0:
                    current_fps = 1.0 / elapsed

                    self.processing_fps = (
                        0.8
                        * self.processing_fps
                        + 0.2
                        * current_fps
                    )

            self.last_processing_wall = now
            self.last_frame_wall = now
            self.frame_count += 1

            self.latest_jpeg = jpeg
            self.frame_width = width
            self.frame_height = height
            self.detections = detections

            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()

        with self.lock:
            frame_age = (
                None
                if self.last_frame_wall is None
                else max(
                    0.0,
                    now - self.last_frame_wall,
                )
            )

            return {
                "service": "online",
                "camera_online": (
                    frame_age is not None
                    and frame_age < 3.0
                ),
                "camera_topic": (
                    self.camera_topic
                ),
                "camera_format": (
                    self.camera_format
                ),
                "frame_age_s": (
                    round(frame_age, 2)
                    if frame_age is not None
                    else None
                ),
                "frame_count": (
                    self.frame_count
                ),
                "processing_fps": round(
                    self.processing_fps,
                    2,
                ),
                "frame_width": (
                    self.frame_width
                ),
                "frame_height": (
                    self.frame_height
                ),
                "detection_count": len(
                    self.detections
                ),
                "detections": list(
                    self.detections
                ),
                "last_capture_path": (
                    self.last_capture_path
                ),
            }

    def save_capture(self) -> Path:
        with self.lock:
            jpeg = self.latest_jpeg

        if jpeg is None:
            raise RuntimeError(
                "No camera frame is available"
            )

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S_%f")

        capture_path = (
            CAPTURE_FOLDER
            / f"inspection_{timestamp}.jpg"
        )

        capture_path.write_bytes(jpeg)

        with self.lock:
            self.last_capture_path = str(
                capture_path
            )

        return capture_path

    def mjpeg_generator(
        self,
    ) -> Generator[bytes, None, None]:
        last_frame: bytes | None = None

        while True:
            with self.condition:
                self.condition.wait(
                    timeout=1.0
                )

                frame = self.latest_jpeg

            if frame is None:
                continue

            if frame == last_frame:
                time.sleep(0.05)

            last_frame = frame

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame
                + b"\r\n"
            )


STATE = VisionState()


class RoboOpsVisionNode(Node):
    def __init__(self) -> None:
        super().__init__(
            "roboops_vision_bridge"
        )

        self.bridge = CvBridge()

        self.camera_subscription = None
        self.camera_topic: str | None = None
        self.last_processed_wall = 0.0

        self.status_publisher = (
            self.create_publisher(
                String,
                "/roboops/vision_status",
                10,
            )
        )

        self.discovery_timer = (
            self.create_timer(
                1.0,
                self.discover_camera,
            )
        )

        self.get_logger().info(
            "RoboOps vision bridge started"
        )

        self.get_logger().info(
            "Searching for a ROS2 camera topic"
        )

    def discover_camera(self) -> None:
        if self.camera_subscription is not None:
            return

        topics = dict(
            self.get_topic_names_and_types()
        )

        raw_candidates = [
            "/intel_realsense_r200_depth/image_raw",
            "/camera/image_raw",
            "/camera/color/image_raw",
            "/camera/rgb/image_raw",
            "/camera/image",
        ]

        compressed_candidates = [
            "/intel_realsense_r200_depth/image_raw/compressed",
            "/camera/image_raw/compressed",
            "/camera/color/image_raw/compressed",
            "/camera/rgb/image_raw/compressed",
        ]

        selected_topic = None
        selected_format = None

        for topic in raw_candidates:
            types = topics.get(
                topic,
                [],
            )

            if (
                "sensor_msgs/msg/Image"
                in types
            ):
                selected_topic = topic
                selected_format = "raw"
                break

        if selected_topic is None:
            for topic, types in topics.items():
                if (
                    "sensor_msgs/msg/Image"
                    in types
                    and (
                        "camera" in topic
                        or "image" in topic
                    )
                    and "depth" not in topic
                ):
                    selected_topic = topic
                    selected_format = "raw"
                    break

        if selected_topic is None:
            for topic in compressed_candidates:
                types = topics.get(
                    topic,
                    [],
                )

                if (
                    "sensor_msgs/msg/CompressedImage"
                    in types
                ):
                    selected_topic = topic
                    selected_format = (
                        "compressed"
                    )
                    break

        if selected_topic is None:
            for topic, types in topics.items():
                if (
                    "sensor_msgs/msg/CompressedImage"
                    in types
                    and "camera" in topic
                    and "depth" not in topic
                ):
                    selected_topic = topic
                    selected_format = (
                        "compressed"
                    )
                    break

        if selected_topic is None:
            return

        self.camera_topic = selected_topic

        if selected_format == "raw":
            self.camera_subscription = (
                self.create_subscription(
                    Image,
                    selected_topic,
                    self.raw_image_callback,
                    qos_profile_sensor_data,
                )
            )
        else:
            self.camera_subscription = (
                self.create_subscription(
                    CompressedImage,
                    selected_topic,
                    self.compressed_image_callback,
                    qos_profile_sensor_data,
                )
            )

        STATE.set_camera(
            selected_topic,
            selected_format,
        )

        self.get_logger().info(
            "Camera connected: "
            f"{selected_topic} "
            f"({selected_format})"
        )

    def raw_image_callback(
        self,
        message: Image,
    ) -> None:
        try:
            frame = (
                self.bridge.imgmsg_to_cv2(
                    message,
                    desired_encoding="bgr8",
                )
            )
        except Exception as error:
            self.get_logger().error(
                f"Image conversion failed: "
                f"{error}"
            )
            return

        self.process_frame(frame)

    def compressed_image_callback(
        self,
        message: CompressedImage,
    ) -> None:
        array = np.frombuffer(
            message.data,
            dtype=np.uint8,
        )

        frame = cv2.imdecode(
            array,
            cv2.IMREAD_COLOR,
        )

        if frame is None:
            return

        self.process_frame(frame)

    def process_frame(
        self,
        frame: np.ndarray,
    ) -> None:
        now = time.monotonic()

        # Limit processing to approximately 5 FPS.
        if (
            now - self.last_processed_wall
            < 0.2
        ):
            return

        self.last_processed_wall = now

        if frame.shape[1] > 800:
            scale = 800 / frame.shape[1]

            frame = cv2.resize(
                frame,
                (
                    800,
                    int(
                        frame.shape[0]
                        * scale
                    ),
                ),
                interpolation=cv2.INTER_AREA,
            )

        annotated, detections = (
            self.detect_objects(frame)
        )

        timestamp_text = datetime.now(
            timezone.utc
        ).strftime("%H:%M:%S UTC")

        cv2.putText(
            annotated,
            timestamp_text,
            (14, 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (245, 245, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            annotated,
            f"Detections: {len(detections)}",
            (14, 53),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (245, 245, 255),
            2,
            cv2.LINE_AA,
        )

        success, encoded = cv2.imencode(
            ".jpg",
            annotated,
            [
                int(
                    cv2.IMWRITE_JPEG_QUALITY
                ),
                82,
            ],
        )

        if not success:
            return

        STATE.update_frame(
            encoded.tobytes(),
            int(annotated.shape[1]),
            int(annotated.shape[0]),
            detections,
        )

        status_message = String()

        status_message.data = json.dumps(
            {
                "camera_topic": (
                    self.camera_topic
                ),
                "detection_count": len(
                    detections
                ),
                "detections": detections,
                "event_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        self.status_publisher.publish(
            status_message
        )

    def detect_objects(
        self,
        frame: np.ndarray,
    ) -> tuple[
        np.ndarray,
        list[dict[str, Any]],
    ]:
        annotated = frame.copy()

        hsv = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2HSV,
        )

        green_mask = cv2.inRange(
            hsv,
            np.array(
                [35, 55, 40],
                dtype=np.uint8,
            ),
            np.array(
                [95, 255, 255],
                dtype=np.uint8,
            ),
        )

        red_mask_low = cv2.inRange(
            hsv,
            np.array(
                [0, 80, 60],
                dtype=np.uint8,
            ),
            np.array(
                [12, 255, 255],
                dtype=np.uint8,
            ),
        )

        red_mask_high = cv2.inRange(
            hsv,
            np.array(
                [168, 80, 60],
                dtype=np.uint8,
            ),
            np.array(
                [180, 255, 255],
                dtype=np.uint8,
            ),
        )

        red_mask = cv2.bitwise_or(
            red_mask_low,
            red_mask_high,
        )

        kernel = np.ones(
            (5, 5),
            dtype=np.uint8,
        )

        green_mask = cv2.morphologyEx(
            green_mask,
            cv2.MORPH_OPEN,
            kernel,
        )

        green_mask = cv2.morphologyEx(
            green_mask,
            cv2.MORPH_CLOSE,
            kernel,
        )

        red_mask = cv2.morphologyEx(
            red_mask,
            cv2.MORPH_OPEN,
            kernel,
        )

        red_mask = cv2.morphologyEx(
            red_mask,
            cv2.MORPH_CLOSE,
            kernel,
        )

        detections: list[
            dict[str, Any]
        ] = []

        detection_sources = [
            (
                "green_structure",
                green_mask,
                (90, 230, 130),
            ),
            (
                "red_marker",
                red_mask,
                (80, 80, 255),
            ),
        ]

        frame_area = float(
            frame.shape[0]
            * frame.shape[1]
        )

        for (
            label,
            mask,
            box_color,
        ) in detection_sources:
            contours, _ = cv2.findContours(
                mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )

            contours = sorted(
                contours,
                key=cv2.contourArea,
                reverse=True,
            )

            accepted = 0

            for contour in contours:
                area = float(
                    cv2.contourArea(
                        contour
                    )
                )

                if area < 500:
                    continue

                x, y, width, height = (
                    cv2.boundingRect(
                        contour
                    )
                )

                if width < 18 or height < 18:
                    continue

                area_ratio = (
                    area / frame_area
                )

                score = min(
                    0.99,
                    0.55
                    + area_ratio * 12.0,
                )

                detection = {
                    "label": label,
                    "score": round(
                        score,
                        3,
                    ),
                    "x": int(x),
                    "y": int(y),
                    "width": int(width),
                    "height": int(height),
                    "area_pixels": int(area),
                }

                detections.append(
                    detection
                )

                cv2.rectangle(
                    annotated,
                    (x, y),
                    (
                        x + width,
                        y + height,
                    ),
                    box_color,
                    2,
                )

                label_text = (
                    f"{label} "
                    f"{score:.2f}"
                )

                cv2.rectangle(
                    annotated,
                    (
                        x,
                        max(
                            0,
                            y - 25,
                        ),
                    ),
                    (
                        x
                        + max(
                            140,
                            len(label_text)
                            * 9,
                        ),
                        y,
                    ),
                    box_color,
                    -1,
                )

                cv2.putText(
                    annotated,
                    label_text,
                    (
                        x + 4,
                        max(
                            17,
                            y - 7,
                        ),
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

                accepted += 1

                if accepted >= 4:
                    break

        detections.sort(
            key=lambda item: (
                item["score"]
            ),
            reverse=True,
        )

        return (
            annotated,
            detections[:8],
        )


ROS_NODE: RoboOpsVisionNode | None = None
ROS_EXECUTOR: SingleThreadedExecutor | None = None
ROS_THREAD: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ROS_NODE
    global ROS_EXECUTOR
    global ROS_THREAD

    rclpy.init(args=None)

    ROS_NODE = RoboOpsVisionNode()

    ROS_EXECUTOR = (
        SingleThreadedExecutor()
    )

    ROS_EXECUTOR.add_node(
        ROS_NODE
    )

    ROS_THREAD = threading.Thread(
        target=ROS_EXECUTOR.spin,
        name="roboops-vision-spin",
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
            ROS_THREAD.join(
                timeout=2.0
            )


app = FastAPI(
    title="RoboOps Vision Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/vision/health")
def vision_health() -> dict[str, Any]:
    return STATE.snapshot()


@app.get("/api/vision/latest")
def vision_latest() -> dict[str, Any]:
    return STATE.snapshot()


@app.post("/api/vision/capture")
def capture_image() -> dict[str, Any]:
    try:
        path = STATE.save_capture()
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return {
        "status": "captured",
        "path": str(path),
        "captured_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "detections": (
            STATE.snapshot()[
                "detections"
            ]
        ),
    }


@app.get("/api/vision/stream")
def camera_stream() -> StreamingResponse:
    return StreamingResponse(
        STATE.mjpeg_generator(),
        media_type=(
            "multipart/x-mixed-replace;"
            "boundary=frame"
        ),
    )
