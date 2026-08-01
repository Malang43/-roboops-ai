from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AllowedAction = Literal[
    "navigate",
    "detect_object",
    "capture_image",
    "inspect_path",
    "return_home",
]


class MissionCreate(BaseModel):
    action: AllowedAction

    target: str | None = Field(
        default=None,
        max_length=100,
        description="Location or object related to the action",
    )


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mission_id: UUID
    action: str
    target: str | None
    status: str
    worker: str | None
    error: str | None
    last_event: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MissionResponse(BaseModel):
    accepted: bool
    mission: MissionRead


class MissionListResponse(BaseModel):
    total: int
    items: list[MissionRead]
