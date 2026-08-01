import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import SessionLocal
from app.db_models import (
    AIPlanRecord,
    AIPlanStep,
    Mission,
)


logger = logging.getLogger(__name__)


FINAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
}


def parse_uuid(
    raw_value: Any,
) -> UUID | None:
    if not raw_value:
        return None

    try:
        return UUID(str(raw_value))
    except ValueError:
        return None


def update_mission_from_ros(
    status_event: dict[str, Any],
) -> None:
    mission_id = parse_uuid(
        status_event.get("mission_id")
    )

    if mission_id is None:
        logger.warning(
            "ROS2 status received without "
            "a valid mission_id"
        )
        return

    with SessionLocal() as database:
        mission = database.get(
            Mission,
            mission_id,
        )

        if mission is None:
            logger.warning(
                "Mission not found: %s",
                mission_id,
            )
            return

        new_status = str(
            status_event.get("status")
            or "unknown"
        )

        mission.status = new_status
        mission.worker = status_event.get(
            "worker"
        )
        mission.error = status_event.get(
            "error"
        )
        mission.last_event = status_event

        now = datetime.now(timezone.utc)

        if (
            new_status == "running"
            and mission.started_at is None
        ):
            mission.started_at = now

        if new_status in FINAL_STATUSES:
            mission.completed_at = now

        plan_id = parse_uuid(
            status_event.get("plan_id")
        )

        if plan_id is not None:
            plan_record = database.get(
                AIPlanRecord,
                plan_id,
            )

            if plan_record is not None:
                if new_status in {
                    "received",
                    "running",
                }:
                    plan_record.status = (
                        "executing"
                    )

                elif new_status == "completed":
                    plan_record.status = (
                        "completed"
                    )

                elif new_status in {
                    "failed",
                    "cancelled",
                }:
                    plan_record.status = (
                        new_status
                    )

            current_step = status_event.get(
                "current_step"
            )

            step_status = status_event.get(
                "step_status"
            )

            if (
                isinstance(current_step, int)
                and step_status
            ):
                step_record = (
                    database.scalar(
                        select(AIPlanStep)
                        .where(
                            AIPlanStep.plan_id
                            == plan_id,
                            AIPlanStep.step_number
                            == current_step,
                        )
                    )
                )

                if step_record is not None:
                    step_record.status = str(
                        step_status
                    )

                    if (
                        step_status == "running"
                        and step_record.started_at
                        is None
                    ):
                        step_record.started_at = (
                            now
                        )

                    if step_status in {
                        "completed",
                        "failed",
                        "cancelled",
                    }:
                        step_record.completed_at = (
                            now
                        )

                    step_record.error = (
                        status_event.get(
                            "error"
                        )
                    )

        database.commit()
