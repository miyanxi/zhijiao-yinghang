from collections import defaultdict
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import LearningRecord, StudentKnowledgeProfile


def rebuild_profiles(db: Session) -> None:
    records = db.scalars(select(LearningRecord).order_by(LearningRecord.occurred_at, LearningRecord.id)).all()
    grouped = defaultdict(list)
    for record in records:
        grouped[(record.student_id, record.knowledge_point_id)].append(record)

    db.execute(delete(StudentKnowledgeProfile))
    for (student_id, knowledge_point_id), items in grouped.items():
        by_assignment = defaultdict(list)
        for item in items:
            by_assignment[item.assignment_id].append(item.is_correct)
        assignment_rates = [sum(values) / len(values) for values in by_assignment.values()]
        recent = assignment_rates[-3:]
        recent_accuracy = sum(recent) / len(recent)
        weak_streak = 0
        for rate in reversed(assignment_rates):
            if rate < 0.7:
                weak_streak += 1
            else:
                break

        if len(assignment_rates) >= 4:
            delta = sum(assignment_rates[-2:]) / 2 - sum(assignment_rates[-4:-2]) / 2
            trend = "上升" if delta > 0.1 else "下降" if delta < -0.1 else "稳定"
        else:
            trend = "样本不足"

        if len(assignment_rates) >= 3 and recent_accuracy < 0.7 and weak_streak >= 2:
            attention = "重点关注"
        elif len(assignment_rates) >= 2 and recent_accuracy < 0.8:
            attention = "观察"
        else:
            attention = "正常" if len(assignment_rates) >= 2 else "样本不足"

        db.add(StudentKnowledgeProfile(
            student_id=student_id,
            knowledge_point_id=knowledge_point_id,
            total_attempts=len(items),
            correct_count=sum(item.is_correct for item in items),
            accuracy=sum(item.is_correct for item in items) / len(items),
            recent_accuracy=recent_accuracy,
            consecutive_weak_count=weak_streak,
            trend=trend,
            attention_status=attention,
            calculated_at=datetime.utcnow(),
        ))
    db.commit()
