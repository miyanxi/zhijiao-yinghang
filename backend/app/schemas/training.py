from datetime import datetime

from pydantic import BaseModel, Field


class TrainingCandidate(BaseModel):
    student_id: int
    student_name: str
    knowledge_point_id: int
    knowledge_point_name: str
    accuracy: float
    recent_accuracy: float
    consecutive_weak_count: int
    total_attempts: int


class ConfirmTrainingRequest(BaseModel):
    student_id: int
    knowledge_point_id: int
    question_count: int = Field(default=10, ge=3, le=20)
    duration_minutes: int = Field(default=15, ge=5, le=60)


class TrainingQuestionUpdate(BaseModel):
    stem: str = Field(min_length=5)
    options: list[str] = Field(min_length=4, max_length=4)
    answer: str
    explanation: str = Field(min_length=1)
    difficulty: str = Field(pattern="^(基础|中等|提高)$")


class TrainingRead(BaseModel):
    id: int
    class_id: int
    student_id: int
    student_name: str
    knowledge_point_id: int
    knowledge_point_name: str
    assignment_id: int | None
    status: str
    source: str | None
    question_count: int
    duration_minutes: int
    baseline_accuracy: float
    baseline_recent_accuracy: float
    current_accuracy: float | None
    current_recent_accuracy: float | None
    training_score: float | None
    training_accuracy: float | None
    questions: list[dict]
    created_at: datetime
