from datetime import datetime

from pydantic import BaseModel, Field


class SubmittedAnswerCreate(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1)


class StudentSubmissionCreate(BaseModel):
    student_id: int
    answers: list[SubmittedAnswerCreate] = Field(min_length=1)


class AssignmentQuestionRead(BaseModel):
    question_id: int
    order_no: int
    type: str
    stem: str
    options: list[str]
    answer: str
    explanation: str
    difficulty: str
    knowledge_point_names: list[str]


class AssignmentRead(BaseModel):
    id: int
    title: str
    assigned_at: datetime
    status: str
    mode: str
    question_count: int
    submission_count: int
    average_score: float | None
    source_draft_id: int | None = None


class StudentAnswerRead(BaseModel):
    question_id: int
    question_stem: str
    knowledge_point_names: list[str]
    answer_text: str
    is_correct: bool
    score: float


class SubmissionRead(BaseModel):
    id: int
    student_id: int
    student_name: str
    submitted_at: datetime
    total_score: float
    answers: list[StudentAnswerRead]


class AssignmentDetailRead(AssignmentRead):
    questions: list[AssignmentQuestionRead]
    submissions: list[SubmissionRead]
