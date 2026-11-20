from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Class, KnowledgePoint, Student, StudentKnowledgeProfile
from ..schemas.training import TrainingCandidate


def training_candidates(class_id: int, db: Session) -> list[TrainingCandidate]:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    rows = db.execute(select(StudentKnowledgeProfile, Student, KnowledgePoint)
        .join(Student, Student.id == StudentKnowledgeProfile.student_id)
        .join(KnowledgePoint, KnowledgePoint.id == StudentKnowledgeProfile.knowledge_point_id)
        .where(Student.class_id == class_id, Student.status == "在读",
               StudentKnowledgeProfile.attention_status == "重点关注")
        .order_by(StudentKnowledgeProfile.recent_accuracy, Student.id)).all()
    return [TrainingCandidate(
        student_id=student.id, student_name=student.name,
        knowledge_point_id=point.id, knowledge_point_name=point.name,
        accuracy=profile.accuracy, recent_accuracy=profile.recent_accuracy,
        consecutive_weak_count=profile.consecutive_weak_count,
        total_attempts=profile.total_attempts,
    ) for profile, student, point in rows]
