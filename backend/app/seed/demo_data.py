from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Class, Student, Teacher


DEMO_STUDENTS = [
    ("张同学", "G1-001"),
    ("李同学", "G1-002"),
    ("王同学", "G1-003"),
    ("赵同学", "G1-004"),
    ("陈同学", "G1-005"),
    ("刘同学", "G1-006"),
]


def seed_demo_data(db: Session) -> None:
    teacher = db.scalar(select(Teacher).where(Teacher.name == "英语教师"))
    if teacher is None:
        teacher = Teacher(name="英语教师")
        db.add(teacher)
        db.flush()

    classroom = db.scalar(
        select(Class).where(Class.teacher_id == teacher.id, Class.name == "高一（3）班")
    )
    if classroom is None:
        classroom = Class(
            name="高一（3）班",
            grade="高一",
            current_topic="谓语动词",
            current_progress="谓语动词专项教学准备阶段",
            teacher_id=teacher.id,
        )
        db.add(classroom)
        db.flush()

    existing = {student.student_no for student in classroom.students}
    for name, student_no in DEMO_STUDENTS:
        if student_no not in existing:
            db.add(Student(name=name, student_no=student_no, class_id=classroom.id))
    db.commit()

