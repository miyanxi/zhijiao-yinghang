from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Class, Student, Teacher
from ..schemas.base import (ClassCreate, ClassDetail, ClassRead, ClassUpdate,
                            StudentCreate, StudentRead)

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("", response_model=list[ClassRead])
def list_classes(db: Session = Depends(get_db)) -> list[Class]:
    return list(db.scalars(select(Class).order_by(Class.id)).all())


@router.post("", response_model=ClassRead, status_code=201)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)) -> Class:
    if not payload.name.strip() or not payload.grade.strip():
        raise HTTPException(status_code=422, detail="班级名称和年级不能为空")
    teacher = db.scalar(select(Teacher).order_by(Teacher.id).limit(1))
    if teacher is None:
        raise HTTPException(status_code=409, detail="尚未配置教师")
    if db.scalar(select(Class.id).where(Class.teacher_id == teacher.id, Class.name == payload.name.strip())):
        raise HTTPException(status_code=409, detail="班级名称已存在")
    classroom = Class(**(payload.model_dump() | {"name": payload.name.strip(), "grade": payload.grade.strip(), "teacher_id": teacher.id}))
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.get("/{class_id}", response_model=ClassDetail)
def get_class(class_id: int, db: Session = Depends(get_db)) -> Class:
    classroom = db.scalar(
        select(Class)
        .options(selectinload(Class.teacher), selectinload(Class.students))
        .where(Class.id == class_id)
    )
    if classroom is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    return classroom


@router.patch("/{class_id}", response_model=ClassRead)
def update_class(class_id: int, payload: ClassUpdate, db: Session = Depends(get_db)) -> Class:
    classroom = db.get(Class, class_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        if changes["name"] is None or not changes["name"].strip():
            raise HTTPException(status_code=422, detail="班级名称不能为空")
        changes["name"] = changes["name"].strip()
        duplicate = db.scalar(select(Class.id).where(Class.teacher_id == classroom.teacher_id, Class.name == changes["name"], Class.id != class_id))
        if duplicate:
            raise HTTPException(status_code=409, detail="班级名称已存在")
    if "grade" in changes:
        if changes["grade"] is None or not changes["grade"].strip():
            raise HTTPException(status_code=422, detail="年级不能为空")
        changes["grade"] = changes["grade"].strip()
    for key, value in changes.items():
        setattr(classroom, key, value)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.get("/{class_id}/students", response_model=list[StudentRead])
def list_class_students(class_id: int, db: Session = Depends(get_db)) -> list[StudentRead]:
    classroom = db.get(Class, class_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    return list(classroom.students)


@router.post("/{class_id}/students", response_model=StudentRead, status_code=201)
def create_student(class_id: int, payload: StudentCreate, db: Session = Depends(get_db)) -> Student:
    if not payload.name.strip() or not payload.student_no.strip():
        raise HTTPException(status_code=422, detail="学生姓名和学号不能为空")
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    student_no = payload.student_no.strip()
    if db.scalar(select(Student.id).where(Student.class_id == class_id, Student.student_no == student_no)):
        raise HTTPException(status_code=409, detail="该班学号已存在")
    student = Student(class_id=class_id, name=payload.name.strip(), student_no=student_no)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student

