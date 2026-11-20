from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    classes: Mapped[list["Class"]] = relationship(back_populates="teacher")


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[str] = mapped_column(String(50), nullable=False)
    current_topic: Mapped[str | None] = mapped_column(String(200))
    current_progress: Mapped[str | None] = mapped_column(Text)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    teacher: Mapped[Teacher] = relationship(back_populates="classes")
    students: Mapped[list["Student"]] = relationship(back_populates="classroom", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    student_no: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="在读", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    classroom: Mapped[Class] = relationship(back_populates="students")


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    questions: Mapped[list["Question"]] = relationship(secondary="question_knowledge_points", back_populates="knowledge_points")


class QuestionKnowledgePoint(Base):
    __tablename__ = "question_knowledge_points"
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), primary_key=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="seed", nullable=False)
    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(secondary="question_knowledge_points", back_populates="questions", overlaps="question_knowledge_points")


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), default="class_unified", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="analyzed", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    questions: Mapped[list["AssignmentQuestion"]] = relationship(back_populates="assignment", order_by="AssignmentQuestion.order_no")


class AssignmentQuestion(Base):
    __tablename__ = "assignment_questions"
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    assignment: Mapped[Assignment] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship()


class StudentSubmission(Base):
    __tablename__ = "student_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    student: Mapped[Student] = relationship()
    answers: Mapped[list["StudentAnswer"]] = relationship(back_populates="submission")


class StudentAnswer(Base):
    __tablename__ = "student_answers"
    __table_args__ = (UniqueConstraint("submission_id", "question_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("student_submissions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    submission: Mapped[StudentSubmission] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()


class LearningRecord(Base):
    __tablename__ = "learning_records"
    __table_args__ = (UniqueConstraint("student_answer_id", "knowledge_point_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    student_answer_id: Mapped[int] = mapped_column(ForeignKey("student_answers.id"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    student_answer: Mapped[StudentAnswer] = relationship()


class StudentKnowledgeProfile(Base):
    __tablename__ = "student_knowledge_profiles"
    __table_args__ = (UniqueConstraint("student_id", "knowledge_point_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    recent_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    consecutive_weak_count: Mapped[int] = mapped_column(Integer, nullable=False)
    trend: Mapped[str] = mapped_column(String(20), nullable=False)
    attention_status: Mapped[str] = mapped_column(String(20), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    knowledge_point: Mapped[KnowledgePoint] = relationship()


class TeachingGoal(Base):
    __tablename__ = "teaching_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    knowledge_point_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    objectives: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    key_points: Mapped[str] = mapped_column(Text, nullable=False)
    difficult_points: Mapped[str] = mapped_column(Text, nullable=False)
    class_context: Mapped[str] = mapped_column(Text, nullable=False)
    teacher_requirements: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def teaching_advice(self) -> str:
        return self.teacher_requirements


class LessonPlan(Base):
    __tablename__ = "lesson_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    teaching_goal_id: Mapped[int] = mapped_column(ForeignKey("teaching_goals.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sections: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    post_review: Mapped["LessonPlanReview | None"] = relationship(
        back_populates="lesson_plan", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def post_evaluation(self) -> str | None:
        return self.post_review.evaluation if self.post_review else None

    @property
    def post_reflection(self) -> str | None:
        return self.post_review.reflection if self.post_review else None

    @property
    def reviewed_at(self) -> datetime | None:
        return self.post_review.updated_at if self.post_review else None


class LessonPlanReview(Base):
    __tablename__ = "lesson_plan_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_plan_id: Mapped[int] = mapped_column(ForeignKey("lesson_plans.id"), unique=True, nullable=False)
    evaluation: Mapped[str] = mapped_column(Text, nullable=False)
    reflection: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    lesson_plan: Mapped[LessonPlan] = relationship(back_populates="post_review")


class AssessmentImport(Base):
    __tablename__ = "assessment_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    paper_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    answer_key_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    paper_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_key_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ready", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UploadedStudentWork(Base):
    __tablename__ = "uploaded_student_works"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessment_imports.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="graded", nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AssignmentStudentWork(Base):
    __tablename__ = "assignment_student_works"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AssignmentDraft(Base):
    __tablename__ = "assignment_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    teaching_goal_id: Mapped[int] = mapped_column(ForeignKey("teaching_goals.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), default="class_unified", nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    questions: Mapped[list["DraftQuestion"]] = relationship(back_populates="draft", order_by="DraftQuestion.order_no", cascade="all, delete-orphan")


class AssignmentPublication(Base):
    __tablename__ = "assignment_publications"
    assignment_draft_id: Mapped[int] = mapped_column(ForeignKey("assignment_drafts.id"), primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), unique=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DraftQuestion(Base):
    __tablename__ = "draft_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_draft_id: Mapped[int] = mapped_column(ForeignKey("assignment_drafts.id"), nullable=False)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(20), default="unchecked", nullable=False)
    quality_issues: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    draft: Mapped[AssignmentDraft] = relationship(back_populates="questions")
    knowledge_point: Mapped[KnowledgePoint] = relationship()


class TargetedTraining(Base):
    __tablename__ = "targeted_trainings"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="confirmed", nullable=False)
    source: Mapped[str | None] = mapped_column(String(20))
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_recent_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    questions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    student: Mapped[Student] = relationship()
    knowledge_point: Mapped[KnowledgePoint] = relationship()
