from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import (
    check_database_connection,
    get_db,
)
from app.db_models import Mission
from app.mission_service import update_mission_from_ros
from app.models import (
    MissionCreate,
    MissionListResponse,
    MissionRead,
    MissionResponse,
)
from app.ros_bridge import RosBridge
from app.routers.planner import router as planner_router


ros_bridge = RosBridge(
    status_handler=update_mission_from_ros,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_connection()
    ros_bridge.start()

    app.state.ros_bridge = ros_bridge

    yield

    ros_bridge.stop()


app = FastAPI(
    title=settings.app_name,
    description=(
        "FastAPI backend for the RoboOps AI platform"
    ),
    version=settings.app_version,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "status": "running",
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "roboops-api",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }


@app.get("/api/database/status")
def database_status(
    database: Session = Depends(get_db),
) -> dict:
    try:
        database.execute(text("SELECT 1"))

        return {
            "connected": True,
            "database": "roboops",
        }
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable",
        ) from error


@app.get("/api/ros/status")
def ros_status() -> dict:
    return {
        "connected": ros_bridge.running,
        "node_name": (
            ros_bridge.node.get_name()
            if ros_bridge.node is not None
            else None
        ),
        "latest_status": (
            ros_bridge.get_latest_status()
        ),
    }


def create_and_publish_mission(
    request: MissionCreate,
    database: Session,
) -> MissionResponse:
    mission = Mission(
        action=request.action,
        target=request.target,
        status="queued",
    )

    database.add(mission)
    database.commit()
    database.refresh(mission)

    mission.status = "sent"
    database.commit()
    database.refresh(mission)

    command = {
        "mission_id": str(mission.id),
        "action": mission.action,
        "target": mission.target,
        "created_at": (
            mission.created_at.isoformat()
        ),
    }

    try:
        ros_bridge.publish_mission(command)
    except RuntimeError as error:
        mission.status = "failed"
        mission.error = str(error)
        mission.completed_at = datetime.now(
            timezone.utc
        )

        database.commit()
        database.refresh(mission)

        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return MissionResponse(
        accepted=True,
        mission=MissionRead.model_validate(mission),
    )


@app.post(
    "/api/missions",
    response_model=MissionResponse,
    status_code=202,
)
def create_mission(
    request: MissionCreate,
    database: Session = Depends(get_db),
) -> MissionResponse:
    return create_and_publish_mission(
        request,
        database,
    )


@app.post(
    "/api/missions/test",
    response_model=MissionResponse,
    status_code=202,
    include_in_schema=False,
)
def create_test_mission(
    request: MissionCreate,
    database: Session = Depends(get_db),
) -> MissionResponse:
    return create_and_publish_mission(
        request,
        database,
    )


@app.get(
    "/api/missions",
    response_model=MissionListResponse,
)
def list_missions(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    database: Session = Depends(get_db),
) -> MissionListResponse:
    statement = (
        select(Mission)
        .order_by(Mission.created_at.desc())
        .limit(limit)
    )

    missions = list(
        database.scalars(statement).all()
    )

    total = database.scalar(
        select(func.count())
        .select_from(Mission)
    )

    return MissionListResponse(
        total=int(total or 0),
        items=[
            MissionRead.model_validate(mission)
            for mission in missions
        ],
    )


@app.get(
    "/api/missions/{mission_id}",
    response_model=MissionRead,
)
def get_mission(
    mission_id: UUID,
    database: Session = Depends(get_db),
) -> MissionRead:
    mission = database.get(
        Mission,
        mission_id,
    )

    if mission is None:
        raise HTTPException(
            status_code=404,
            detail="Mission not found",
        )

    return MissionRead.model_validate(mission)


app.include_router(planner_router)
