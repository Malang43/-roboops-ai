from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import AllowedAction


RiskLevel = Literal[
    "low",
    "medium",
    "high",
]


class NaturalLanguageMissionRequest(BaseModel):
    prompt: str = Field(
        min_length=5,
        max_length=1000,
    )


class MissionPlanStep(BaseModel):
    step_number: int = Field(
        ge=1,
        le=8,
    )

    action: AllowedAction

    target: str | None = Field(
        default=None,
        max_length=100,
    )

    description: str = Field(
        min_length=3,
        max_length=250,
    )


class MissionPlan(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=100,
    )

    summary: str = Field(
        min_length=5,
        max_length=500,
    )

    risk_level: RiskLevel
    requires_approval: bool

    assumptions: list[str] = Field(
        max_length=8,
    )

    steps: list[MissionPlanStep] = Field(
        min_length=1,
        max_length=8,
    )


class MissionPlanResponse(BaseModel):
    plan_id: UUID
    status: str
    prompt: str
    provider: str
    model: str
    plan: MissionPlan


class MissionPlanApprovalResponse(BaseModel):
    approved: bool
    plan_id: UUID
    mission_id: UUID
    plan_status: str
    mission_status: str
    message: str
