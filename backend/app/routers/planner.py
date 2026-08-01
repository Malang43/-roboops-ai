import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.db_models import (
    AIPlanRecord,
    AIPlanStep,
    Mission,
)
from app.llm_models import (
    MissionPlanApprovalResponse,
    MissionPlanResponse,
    NaturalLanguageMissionRequest,
)
from app.llm_service import (
    MissionPlanGenerationError,
    OllamaUnavailableError,
    mission_planner,
)
from app.ros_bridge import RosBridge


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api",
    tags=["Local AI Mission Planner"],
)


def get_ros_bridge() -> RosBridge:
    from app.main import ros_bridge

    return ros_bridge


@router.get("/llm/status")
def get_llm_status() -> dict:
    return {
        "provider": "Ollama",
        "model": settings.ollama_model,
        "base_url": settings.ollama_base_url,
    }


@router.post(
    "/mission-plans",
    response_model=MissionPlanResponse,
)
def generate_mission_plan(
    request: NaturalLanguageMissionRequest,
    database: Session = Depends(get_db),
) -> MissionPlanResponse:
    try:
        plan = mission_planner.generate_plan(
            request.prompt,
        )

    except OllamaUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except MissionPlanGenerationError as error:
        logger.exception(
            "Mission-plan generation failed"
        )

        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception(
            "Unexpected local LLM error"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "An unexpected mission-planning "
                "error occurred"
            ),
        ) from error

    plan_record = AIPlanRecord(
        prompt=request.prompt,
        title=plan.title,
        summary=plan.summary,
        risk_level=plan.risk_level,
        requires_approval=True,
        assumptions=plan.assumptions,
        provider="Ollama",
        model=settings.ollama_model,
        status="awaiting_approval",
    )

    database.add(plan_record)
    database.flush()

    for step in plan.steps:
        database.add(
            AIPlanStep(
                plan_id=plan_record.id,
                step_number=step.step_number,
                action=step.action,
                target=step.target,
                description=step.description,
                status="pending",
            )
        )

    database.commit()
    database.refresh(plan_record)

    return MissionPlanResponse(
        plan_id=plan_record.id,
        status=plan_record.status,
        prompt=request.prompt,
        provider=plan_record.provider,
        model=plan_record.model,
        plan=plan,
    )


@router.post(
    "/mission-plans/{plan_id}/approve",
    response_model=MissionPlanApprovalResponse,
    status_code=202,
)
def approve_mission_plan(
    plan_id: UUID,
    database: Session = Depends(get_db),
    ros_bridge: RosBridge = Depends(
        get_ros_bridge
    ),
) -> MissionPlanApprovalResponse:
    plan_record = database.get(
        AIPlanRecord,
        plan_id,
    )

    if plan_record is None:
        raise HTTPException(
            status_code=404,
            detail="Mission plan not found",
        )

    if plan_record.status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=(
                "This mission plan has already "
                "been approved or processed"
            ),
        )

    steps = list(
        database.scalars(
            select(AIPlanStep)
            .where(
                AIPlanStep.plan_id == plan_id
            )
            .order_by(
                AIPlanStep.step_number
            )
        ).all()
    )

    if not steps:
        raise HTTPException(
            status_code=409,
            detail=(
                "The mission plan contains no steps"
            ),
        )

    mission = Mission(
        action="execute_plan",
        target=plan_record.title,
        status="sent",
        last_event={
            "plan_id": str(plan_id),
            "status": "approved",
        },
    )

    database.add(mission)
    database.flush()

    plan_record.mission_id = mission.id
    plan_record.status = "executing"
    plan_record.approved_at = datetime.now(
        timezone.utc
    )

    database.commit()
    database.refresh(mission)

    command = {
        "mission_id": str(mission.id),
        "plan_id": str(plan_record.id),
        "action": "execute_plan",
        "target": plan_record.title,
        "title": plan_record.title,
        "total_steps": len(steps),
        "steps": [
            {
                "step_number": step.step_number,
                "action": step.action,
                "target": step.target,
                "description": step.description,
            }
            for step in steps
        ],
    }

    try:
        ros_bridge.publish_mission(command)

    except RuntimeError as error:
        mission.status = "failed"
        mission.error = str(error)
        mission.completed_at = datetime.now(
            timezone.utc
        )

        plan_record.status = "failed"

        database.commit()

        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return MissionPlanApprovalResponse(
        approved=True,
        plan_id=plan_record.id,
        mission_id=mission.id,
        plan_status=plan_record.status,
        mission_status=mission.status,
        message=(
            "Mission plan approved and sent "
            "to ROS2"
        ),
    )
