from typing import Literal

from pydantic import BaseModel, Field


ManagerIntent = Literal[
    "class_analysis", "student_analysis", "lesson_prep",
    "class_assignment", "targeted_training", "unsupported",
]


class ManagerRequest(BaseModel):
    class_id: int
    message: str = Field(min_length=4, max_length=500)


class ManagerIntentData(BaseModel):
    intent: ManagerIntent
    student_name: str | None = None
    knowledge_point_name: str | None = None
    duration_minutes: int | None = None
    question_count: int | None = None


class ManagerSummaryData(BaseModel):
    summary: str = Field(min_length=1, max_length=600)


class ManagerMetric(BaseModel):
    label: str
    value: str


class ManagerAction(BaseModel):
    view: Literal["analytics", "student-detail", "goals", "lesson-plans", "smart-assignments", "training"]
    label: str
    requires_confirmation: bool = False
    student_id: int | None = None
    knowledge_point_id: int | None = None
    duration_minutes: int | None = None
    question_count: int | None = None


class ManagerResponse(BaseModel):
    intent: ManagerIntent
    source: Literal["demo", "deepseek", "program"]
    title: str
    summary: str
    metrics: list[ManagerMetric] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    action: ManagerAction | None = None
