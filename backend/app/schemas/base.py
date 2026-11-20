from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TeacherRead(ORMModel):
    id: int
    name: str
    created_at: datetime


class StudentRead(ORMModel):
    id: int
    name: str
    student_no: str
    class_id: int
    status: str
    created_at: datetime


class ClassRead(ORMModel):
    id: int
    name: str
    grade: str
    current_topic: str | None
    current_progress: str | None
    teacher_id: int
    created_at: datetime


class ClassDetail(ClassRead):
    teacher: TeacherRead
    students: list[StudentRead]


class HealthRead(BaseModel):
    status: str
    database: str


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    grade: str = Field(min_length=1, max_length=50)
    current_topic: str | None = Field(default=None, max_length=200)
    current_progress: str | None = None


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    grade: str | None = Field(default=None, min_length=1, max_length=50)
    current_topic: str | None = Field(default=None, max_length=200)
    current_progress: str | None = None


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    student_no: str = Field(min_length=1, max_length=50)


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    student_no: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=20)

