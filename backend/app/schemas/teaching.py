from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GoalParseRequest(BaseModel):
    class_id: int
    raw_input: str = Field(min_length=5, max_length=3000)


class KnowledgePointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="课程内容", min_length=1, max_length=50)


class GoalDraftData(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    knowledge_point_ids: list[int] = Field(default_factory=list)
    objectives: list[str] = Field(min_length=1)
    key_points: str
    difficult_points: str
    class_context: str
    teaching_advice: str = ""
    # Kept for compatibility with goals created by earlier builds.
    teacher_requirements: str | None = None


class GoalParseResult(GoalDraftData):
    source: str


class GoalCreate(GoalDraftData):
    class_id: int
    raw_input: str = Field(min_length=1)
    source: str = Field(pattern="^(demo|deepseek|teacher)$")


class GoalUpdate(BaseModel):
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    knowledge_point_ids: list[int] | None = None
    objectives: list[str] | None = None
    key_points: str | None = None
    difficult_points: str | None = None
    class_context: str | None = None
    teaching_advice: str | None = None
    teacher_requirements: str | None = None


class GoalRead(GoalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime


class LessonSection(BaseModel):
    key: str
    title: str
    content: str
    duration_minutes: int = Field(ge=0, le=180)


class LessonPlanGenerated(BaseModel):
    title: str
    sections: list[LessonSection] = Field(min_length=1)


class LessonPlanGenerateRequest(BaseModel):
    teaching_goal_id: int
    difficulty: str = Field(default="中等", pattern="^(基础|中等|提高)$")
    duration_minutes: int = Field(default=45, ge=20, le=120)


class LessonPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_id: int
    teaching_goal_id: int
    title: str
    sections: list[LessonSection]
    difficulty: str
    duration_minutes: int
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    post_evaluation: str | None = None
    post_reflection: str | None = None
    reviewed_at: datetime | None = None


class LessonSectionUpdate(BaseModel):
    content: str = Field(min_length=1)
    duration_minutes: int = Field(ge=0, le=180)


class LessonPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    difficulty: str | None = Field(default=None, pattern="^(基础|中等|提高)$")
    duration_minutes: int | None = Field(default=None, ge=20, le=120)


class LessonPlanReviewUpdate(BaseModel):
    evaluation: str = Field(min_length=1, max_length=5000)
    reflection: str = Field(min_length=1, max_length=5000)


class DraftQuestionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: str = Field(pattern="^(single_choice|multiple_choice|fill_blank)$")
    stem: str = Field(min_length=5)
    options: list[str] = Field(default_factory=list, max_length=4)
    answer: str
    explanation: str = Field(min_length=1)
    knowledge_point_id: int
    difficulty: str = Field(pattern="^(基础|中等|提高)$")

    @property
    def answer_values(self) -> list[str]:
        return [item for item in self.answer.split("||") if item]


class GeneratedQuestions(BaseModel):
    title: str
    questions: list[DraftQuestionData] = Field(min_length=1)


class AssignmentDraftGenerateRequest(BaseModel):
    teaching_goal_id: int
    question_count: int = Field(default=5, ge=3, le=20)
    difficulty: str = Field(default="中等", pattern="^(基础|中等|提高)$")


class DraftQuestionUpdate(BaseModel):
    stem: str | None = Field(default=None, min_length=5)
    options: list[str] | None = Field(default=None, max_length=4)
    answer: str | None = None
    explanation: str | None = Field(default=None, min_length=1)
    knowledge_point_id: int | None = None
    difficulty: str | None = Field(default=None, pattern="^(基础|中等|提高)$")


class DraftQuestionRead(DraftQuestionData):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_no: int
    quality_status: str
    quality_issues: list[str]


class AssignmentDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_id: int
    teaching_goal_id: int
    title: str
    mode: str
    difficulty: str
    status: str
    source: str
    created_at: datetime
    questions: list[DraftQuestionRead]


class QualityReviewResult(BaseModel):
    issues: list[str]
