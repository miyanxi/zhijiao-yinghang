from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import Student
from ..schemas.base import StudentRead, StudentUpdate

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}", response_model=StudentRead)
def get_student(student_id: int, db: Session = Depends(get_db)) -> Student:
    student = db.scalar(select(Student).where(Student.id == student_id))
    if student is None:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="学生不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        if changes["name"] is None or not changes["name"].strip():
            raise HTTPException(status_code=422, detail="学生姓名不能为空")
        changes["name"] = changes["name"].strip()
    if "student_no" in changes:
        if changes["student_no"] is None or not changes["student_no"].strip():
            raise HTTPException(status_code=422, detail="学号不能为空")
        changes["student_no"] = changes["student_no"].strip()
        duplicate = db.scalar(select(Student.id).where(Student.class_id == student.class_id, Student.student_no == changes["student_no"], Student.id != student_id))
        if duplicate:
            raise HTTPException(status_code=409, detail="该班学号已存在")
    for key, value in changes.items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return student

