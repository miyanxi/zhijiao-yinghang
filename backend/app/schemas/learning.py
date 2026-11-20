from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgePointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    knowledge_point_id: int
    total_attempts: int
    correct_count: int
    accuracy: float
    recent_accuracy: float
    consecutive_weak_count: int
    trend: str
    attention_status: str
    calculated_at: datetime
    knowledge_point: KnowledgePointRead


class LearningRecordRead(BaseModel):
    id: int
    assignment_id: int
    assignment_title: str
    question_id: int
    knowledge_point_id: int
    knowledge_point_name: str
    is_correct: bool
    answer_text: str
    score: float
    occurred_at: datetime
    demo_simulated: bool = False


class AssignmentSummaryRead(BaseModel):
    id: int
    title: str
    assigned_at: datetime
    status: str
    mode: str


class ClassKnowledgePointSummary(BaseModel):
    knowledge_point_id: int
    name: str
    category: str
    attempts: int
    correct_count: int
    accuracy: float


class ScoreTrendPoint(BaseModel):
    assignment_id: int
    title: str
    assigned_at: datetime
    score: float | None
    submission_count: int | None = None


class TeachingNoteRead(BaseModel):
    lesson_plan_id: int
    title: str
    evaluation: str
    reflection: str
    updated_at: datetime


class ClassLearningOverview(BaseModel):
    class_id: int
    assignment_count: int
    average_score: float | None
    completion_rate: float
    knowledge_points: list[ClassKnowledgePointSummary]
    attention_students: int
    error_count: int
    score_trend: list[ScoreTrendPoint]
    teaching_notes: list[TeachingNoteRead] = []
    demo_submission_count: int = 0


class StudentLearningOverview(BaseModel):
    student_id: int
    assignment_count: int
    average_score: float | None
    completion_rate: float
    profiles: list[ProfileRead]
    recent_assignments: list[AssignmentSummaryRead]
    records: list[LearningRecordRead]
    score_trend: list[ScoreTrendPoint]
