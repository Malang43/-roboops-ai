import json
import os
import threading
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from textwrap import wrap
from typing import Any

import rclpy
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String as SQLString,
    Text,
    create_engine,
    desc,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from std_msgs.msg import String as RosString


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    (
        "postgresql+psycopg://"
        "roboops_app:roboops_app@"
        "127.0.0.1:5433/roboops"
    ),
)

REPORT_FOLDER = Path(
    "/srv/roboops-ai/data/reports"
)

CAPTURE_FOLDER = Path(
    "/srv/roboops-ai/data/captures"
)

REPORT_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)

CAPTURE_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)


class Base(DeclarativeBase):
    pass


class MissionReport(Base):
    __tablename__ = "mission_reports"

    mission_id: Mapped[str] = mapped_column(
        SQLString(64),
        primary_key=True,
    )

    plan_id: Mapped[str | None] = mapped_column(
        SQLString(64),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        SQLString(32),
        nullable=False,
        index=True,
    )

    action: Mapped[str | None] = mapped_column(
        SQLString(100),
        nullable=True,
    )

    target: Mapped[str | None] = mapped_column(
        SQLString(255),
        nullable=True,
    )

    progress_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    current_step: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_steps: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    detection_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    detected_labels: Mapped[list[Any]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    detections: Mapped[list[Any]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    capture_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    report_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    event_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

Base.metadata.create_all(engine)


class ReportState:
    def __init__(self) -> None:
        self.lock = threading.Lock()

        self.data: dict[str, Any] = {
            "service": "starting",
            "received_status_events": 0,
            "terminal_events_detected": 0,
            "reports_generated": 0,
            "report_failures": 0,
            "last_mission_id": None,
            "last_report_path": None,
            "last_error": None,
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
                int(self.data.get(field, 0))
                + 1
            )

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return deepcopy(self.data)


STATE = ReportState()


def parse_datetime(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:
        return None


def safe_text(
    value: Any,
) -> str:
    if value is None:
        return "N/A"

    if isinstance(
        value,
        (dict, list),
    ):
        return json.dumps(
            value,
            ensure_ascii=False,
        )

    return str(value)


def create_pdf_report(
    payload: dict[str, Any],
) -> Path:
    mission_id = str(
        payload["mission_id"]
    )

    output_path = (
        REPORT_FOLDER
        / f"mission_{mission_id}.pdf"
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=(
            f"RoboOps Mission Report "
            f"{mission_id}"
        ),
    )

    styles = getSampleStyleSheet()

    story: list[Any] = []

    story.append(
        Paragraph(
            "RoboOps AI Mission Report",
            styles["Title"],
        )
    )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    status = str(
        payload.get("status")
        or "unknown"
    ).upper()

    summary_rows = [
        [
            "Result",
            status,
        ],
        [
            "Mission ID",
            mission_id,
        ],
        [
            "Plan ID",
            safe_text(
                payload.get("plan_id")
            ),
        ],
        [
            "Action",
            safe_text(
                payload.get("action")
            ),
        ],
        [
            "Target",
            safe_text(
                payload.get("target")
            ),
        ],
        [
            "Progress",
            str(payload.get("progress_percent", 0)) + "%",
        ],
        [
            "Mission steps",
            (
                str(payload.get("current_step", "N/A"))
                + " / "
                + str(payload.get("total_steps", 0))
            ),
        ],
        [
            "Detection count",
            safe_text(
                payload.get(
                    "detection_count",
                    0,
                )
            ),
        ],
        [
            "Detected labels",
            ", ".join(
                payload.get(
                    "detected_labels"
                )
                or []
            )
            or "None",
        ],
        [
            "Capture evidence",
            safe_text(
                payload.get("capture_path")
            ),
        ],
        [
            "Error",
            safe_text(
                payload.get("error")
            ),
        ],
        [
            "Robot event time",
            safe_text(
                payload.get("event_at")
            ),
        ],
        [
            "Report generated",
            datetime.now(
                timezone.utc
            ).isoformat(),
        ],
    ]

    summary_table = Table(
        summary_rows,
        colWidths=[
            45 * mm,
            120 * mm,
        ],
        repeatRows=0,
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#19223A"
                    ),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (0, -1),
                    colors.white,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#B9C1D3"
                    ),
                ),
                (
                    "ROWBACKGROUNDS",
                    (1, 0),
                    (1, -1),
                    [
                        colors.HexColor(
                            "#F5F7FB"
                        ),
                        colors.white,
                    ],
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(summary_table)

    detections = (
        payload.get("detections")
        or []
    )

    if detections:
        story.append(
            Spacer(
                1,
                8 * mm,
            )
        )

        story.append(
            Paragraph(
                "Computer Vision Detections",
                styles["Heading2"],
            )
        )

        detection_rows = [
            [
                "Label",
                "Score",
                "Bounding box",
                "Area",
            ]
        ]

        for detection in detections:
            detection_rows.append(
                [
                    safe_text(
                        detection.get("label")
                    ),
                    safe_text(
                        detection.get("score")
                    ),
                    (
                        f"{detection.get('x', 'N/A')}, "
                        f"{detection.get('y', 'N/A')} — "
                        f"{detection.get('width', 'N/A')} × "
                        f"{detection.get('height', 'N/A')}"
                    ),
                    safe_text(
                        detection.get(
                            "area_pixels"
                        )
                    ),
                ]
            )

        detection_table = Table(
            detection_rows,
            colWidths=[
                43 * mm,
                28 * mm,
                62 * mm,
                30 * mm,
            ],
            repeatRows=1,
        )

        detection_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor(
                            "#6657FF"
                        ),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold",
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor(
                            "#B9C1D3"
                        ),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor(
                                "#F3F5FA"
                            ),
                        ],
                    ),
                ]
            )
        )

        story.append(
            detection_table
        )

    story.append(
        Spacer(
            1,
            8 * mm,
        )
    )

    story.append(
        Paragraph(
            "System Evidence",
            styles["Heading2"],
        )
    )

    evidence_lines = [
        (
            "Mission execution was performed "
            "through ROS2 and Nav2."
        ),
        (
            "Robot motion was simulated using "
            "Gazebo physics and sensors."
        ),
        (
            "Computer-vision results were obtained "
            "from the simulated robot camera."
        ),
        (
            "The terminal mission event was "
            "delivered to the n8n automation workflow."
        ),
    ]

    for line in evidence_lines:
        story.append(
            Paragraph(
                f"• {line}",
                styles["BodyText"],
            )
        )

        story.append(
            Spacer(
                1,
                2 * mm,
            )
        )

    document.build(story)

    return output_path


def serialize_report(
    report: MissionReport,
) -> dict[str, Any]:
    return {
        "mission_id": report.mission_id,
        "plan_id": report.plan_id,
        "status": report.status,
        "action": report.action,
        "target": report.target,
        "progress_percent": (
            report.progress_percent
        ),
        "current_step": report.current_step,
        "total_steps": report.total_steps,
        "detection_count": (
            report.detection_count
        ),
        "detected_labels": (
            report.detected_labels
            or []
        ),
        "detections": (
            report.detections
            or []
        ),
        "capture_path": (
            report.capture_path
        ),
        "report_path": (
            report.report_path
        ),
        "error": report.error,
        "event_at": (
            report.event_at.isoformat()
            if report.event_at
            else None
        ),
        "created_at": (
            report.created_at.isoformat()
            if report.created_at
            else None
        ),
        "updated_at": (
            report.updated_at.isoformat()
            if report.updated_at
            else None
        ),
        "report_download_url": (
            f"/api/reports/"
            f"{report.mission_id}/download"
        ),
        "evidence_download_url": (
            f"/api/reports/"
            f"{report.mission_id}/evidence"
            if report.capture_path
            else None
        ),
    }


class RoboOpsReportNode(Node):
    def __init__(self) -> None:
        super().__init__(
            "roboops_report_service"
        )

        self.mission_context: dict[
            str,
            dict[str, Any],
        ] = {}

        self.processed_terminal_events: set[
            tuple[str, str]
        ] = set()

        self.create_subscription(
            RosString,
            "/roboops/mission_status",
            self.status_callback,
            30,
        )

        STATE.update(
            {
                "service": "online",
            }
        )

        self.get_logger().info(
            "RoboOps report service started"
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
        message: RosString,
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
            payload.get("mission_id")
            or ""
        ).strip()

        if not mission_id:
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
            payload.get("status")
            or ""
        ).strip().lower()

        if status not in {
            "completed",
            "failed",
        }:
            return

        terminal_key = (
            mission_id,
            status,
        )

        if terminal_key in (
            self.processed_terminal_events
        ):
            return

        self.processed_terminal_events.add(
            terminal_key
        )

        STATE.increment(
            "terminal_events_detected"
        )

        final_payload = deepcopy(
            context
        )

        final_payload.update(
            {
                "mission_id": mission_id,
                "status": status,
            }
        )

        try:
            report_path = create_pdf_report(
                final_payload
            )

            with SessionLocal() as session:
                report = session.get(
                    MissionReport,
                    mission_id,
                )

                if report is None:
                    report = MissionReport(
                        mission_id=mission_id,
                        status=status,
                    )

                    session.add(report)

                report.plan_id = (
                    final_payload.get(
                        "plan_id"
                    )
                )

                report.status = status

                report.action = (
                    final_payload.get(
                        "action"
                    )
                )

                report.target = (
                    final_payload.get(
                        "target"
                    )
                )

                report.progress_percent = int(
                    final_payload.get(
                        "progress_percent",
                        0,
                    )
                    or 0
                )

                report.current_step = (
                    final_payload.get(
                        "current_step"
                    )
                )

                report.total_steps = int(
                    final_payload.get(
                        "total_steps",
                        0,
                    )
                    or 0
                )

                report.detection_count = int(
                    final_payload.get(
                        "detection_count",
                        0,
                    )
                    or 0
                )

                report.detected_labels = (
                    final_payload.get(
                        "detected_labels"
                    )
                    or []
                )

                report.detections = (
                    final_payload.get(
                        "detections"
                    )
                    or []
                )

                report.capture_path = (
                    final_payload.get(
                        "capture_path"
                    )
                )

                report.report_path = str(
                    report_path
                )

                report.error = (
                    final_payload.get(
                        "error"
                    )
                )

                report.event_payload = (
                    final_payload
                )

                report.event_at = parse_datetime(
                    final_payload.get(
                        "event_at"
                    )
                )

                report.updated_at = datetime.now(
                    timezone.utc
                )

                session.commit()

            STATE.increment(
                "reports_generated"
            )

            STATE.update(
                {
                    "last_mission_id": (
                        mission_id
                    ),
                    "last_report_path": str(
                        report_path
                    ),
                    "last_error": None,
                }
            )

            self.get_logger().info(
                "Mission PDF report generated: "
                f"{report_path}"
            )

        except Exception as error:
            STATE.increment(
                "report_failures"
            )

            STATE.update(
                {
                    "last_mission_id": (
                        mission_id
                    ),
                    "last_error": str(
                        error
                    ),
                }
            )

            self.get_logger().error(
                "Report generation failed: "
                f"{error}"
            )


ROS_NODE: RoboOpsReportNode | None = None
ROS_EXECUTOR: SingleThreadedExecutor | None = None
ROS_THREAD: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ROS_NODE
    global ROS_EXECUTOR
    global ROS_THREAD

    rclpy.init(args=None)

    ROS_NODE = RoboOpsReportNode()

    ROS_EXECUTOR = (
        SingleThreadedExecutor()
    )

    ROS_EXECUTOR.add_node(
        ROS_NODE
    )

    ROS_THREAD = threading.Thread(
        target=ROS_EXECUTOR.spin,
        name="roboops-report-ros-spin",
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
    title="RoboOps Mission Reports",
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


@app.get("/api/reports/health")
def report_health() -> dict[str, Any]:
    state = STATE.snapshot()

    with SessionLocal() as session:
        report_count = session.query(
            MissionReport
        ).count()

    state["stored_reports"] = (
        report_count
    )

    return state


@app.get("/api/reports")
def list_reports(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
) -> dict[str, Any]:
    with SessionLocal() as session:
        reports = session.scalars(
            select(MissionReport)
            .order_by(
                desc(
                    MissionReport.created_at
                )
            )
            .limit(limit)
        ).all()

        return {
            "items": [
                serialize_report(report)
                for report in reports
            ],
            "count": len(reports),
        }


@app.get("/api/reports/{mission_id}")
def get_report(
    mission_id: str,
) -> dict[str, Any]:
    with SessionLocal() as session:
        report = session.get(
            MissionReport,
            mission_id,
        )

        if report is None:
            raise HTTPException(
                status_code=404,
                detail="Mission report not found",
            )

        return serialize_report(report)


@app.get(
    "/api/reports/{mission_id}/download"
)
def download_report(
    mission_id: str,
) -> FileResponse:
    with SessionLocal() as session:
        report = session.get(
            MissionReport,
            mission_id,
        )

        if (
            report is None
            or not report.report_path
        ):
            raise HTTPException(
                status_code=404,
                detail="PDF report not found",
            )

        report_path = Path(
            report.report_path
        ).resolve()

    if (
        not report_path.exists()
        or REPORT_FOLDER.resolve()
        not in report_path.parents
    ):
        raise HTTPException(
            status_code=404,
            detail="PDF report file not found",
        )

    return FileResponse(
        path=str(report_path),
        filename=report_path.name,
        media_type="application/pdf",
    )


@app.get(
    "/api/reports/{mission_id}/evidence"
)
def download_evidence(
    mission_id: str,
) -> FileResponse:
    with SessionLocal() as session:
        report = session.get(
            MissionReport,
            mission_id,
        )

        if (
            report is None
            or not report.capture_path
        ):
            raise HTTPException(
                status_code=404,
                detail="Capture evidence not found",
            )

        capture_path = Path(
            report.capture_path
        ).resolve()

    if (
        not capture_path.exists()
        or CAPTURE_FOLDER.resolve()
        not in capture_path.parents
    ):
        raise HTTPException(
            status_code=404,
            detail="Capture evidence file not found",
        )

    return FileResponse(
        path=str(capture_path),
        filename=capture_path.name,
        media_type="image/jpeg",
    )
