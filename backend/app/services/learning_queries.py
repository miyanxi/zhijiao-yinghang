from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (Assignment, AssignmentStudentWork, Class, KnowledgePoint, LearningRecord, LessonPlan,
                      LessonPlanReview, Student, StudentAnswer,
                      StudentKnowledgeProfile, StudentSubmission)
from .demo_upload import DEMO_UPLOAD_MARKER
from ..schemas.learning import (ClassKnowledgePointSummary, ClassLearningOverview,
                                LearningRecordRead, ProfileRead, ScoreTrendPoint,
                                StudentLearningOverview, TeachingNoteRead)


def class_learning_overview(class_id: int, db: Session) -> ClassLearningOverview:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    assignments = db.scalars(select(Assignment).where(
        Assignment.class_id == class_id, Assignment.mode == "class_unified"
    ).order_by(Assignment.assigned_at)).all()
    students = db.scalars(select(Student).where(Student.class_id == class_id)).all()
    submissions = db.scalars(select(StudentSubmission).join(Assignment).where(
        Assignment.class_id == class_id, Assignment.mode == "class_unified"
    )).all()
    demo_submission_count = db.scalar(select(func.count()).select_from(AssignmentStudentWork)
        .join(Assignment, Assignment.id == AssignmentStudentWork.assignment_id)
        .where(Assignment.class_id == class_id, AssignmentStudentWork.status == "graded",
               AssignmentStudentWork.extracted_text == DEMO_UPLOAD_MARKER)) or 0
    records = db.scalars(select(LearningRecord).join(Student).join(
        Assignment, Assignment.id == LearningRecord.assignment_id
    ).where(Student.class_id == class_id, Assignment.mode == "class_unified")).all()
    point_map = {point.id: point for point in db.scalars(select(KnowledgePoint)).all()}
    grouped = defaultdict(list)
    for record in records:
        grouped[record.knowledge_point_id].append(record.is_correct)
    summaries = [ClassKnowledgePointSummary(
        knowledge_point_id=point_id,
        name=point_map[point_id].name,
        category=point_map[point_id].category,
        attempts=len(values),
        correct_count=sum(values),
        accuracy=sum(values) / len(values),
    ) for point_id, values in grouped.items()]
    scores = [submission.total_score for submission in submissions]
    attention_count = db.scalar(
        select(func.count(func.distinct(StudentKnowledgeProfile.student_id)))
        .join(Student, Student.id == StudentKnowledgeProfile.student_id)
        .where(Student.class_id == class_id, StudentKnowledgeProfile.attention_status == "重点关注")
    ) or 0
    expected = len(students) * len(assignments)
    assignment_scores = defaultdict(list)
    for submission in submissions:
        assignment_scores[submission.assignment_id].append(submission.total_score)
    teaching_notes = [TeachingNoteRead(
        lesson_plan_id=plan.id,
        title=plan.title,
        evaluation=review.evaluation,
        reflection=review.reflection,
        updated_at=review.updated_at,
    ) for plan, review in db.execute(
        select(LessonPlan, LessonPlanReview)
        .join(LessonPlanReview, LessonPlanReview.lesson_plan_id == LessonPlan.id)
        .where(LessonPlan.class_id == class_id)
        .order_by(LessonPlanReview.updated_at.desc())
        .limit(5)
    ).all()]
    return ClassLearningOverview(
        class_id=class_id,
        assignment_count=len(assignments),
        average_score=sum(scores) / len(scores) if scores else None,
        completion_rate=len(submissions) / expected if expected else 0,
        knowledge_points=sorted(summaries, key=lambda item: item.accuracy),
        attention_students=attention_count,
        error_count=sum(not record.is_correct for record in records),
        score_trend=[ScoreTrendPoint(
            assignment_id=item.id, title=item.title, assigned_at=item.assigned_at,
            score=sum(assignment_scores[item.id]) / len(assignment_scores[item.id]) if assignment_scores[item.id] else None,
            submission_count=len(assignment_scores[item.id]),
        ) for item in assignments[-6:]],
        teaching_notes=teaching_notes,
        demo_submission_count=demo_submission_count,
    )


def student_learning_overview(student_id: int, db: Session) -> StudentLearningOverview:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="学生不存在")
    submissions = db.scalars(select(StudentSubmission).join(Assignment).where(
        StudentSubmission.student_id == student_id, Assignment.mode == "class_unified"
    ).order_by(Assignment.assigned_at.desc())).all()
    assignment_count = db.scalar(select(func.count()).select_from(Assignment).where(
        Assignment.class_id == student.class_id, Assignment.mode == "class_unified"
    )) or 0
    profiles = db.scalars(select(StudentKnowledgeProfile)
        .options(selectinload(StudentKnowledgeProfile.knowledge_point))
        .where(StudentKnowledgeProfile.student_id == student_id)
        .order_by(StudentKnowledgeProfile.attention_status.desc(), StudentKnowledgeProfile.accuracy)).all()
    records = db.execute(select(LearningRecord, Assignment.title, KnowledgePoint.name)
        .options(selectinload(LearningRecord.student_answer))
        .join(Assignment, Assignment.id == LearningRecord.assignment_id)
        .join(KnowledgePoint, KnowledgePoint.id == LearningRecord.knowledge_point_id)
        .join(StudentAnswer, StudentAnswer.id == LearningRecord.student_answer_id)
        .where(LearningRecord.student_id == student_id)
        .order_by(LearningRecord.occurred_at.desc()).limit(20)).all()
    demo_assignment_ids = set(db.scalars(select(AssignmentStudentWork.assignment_id).where(
        AssignmentStudentWork.student_id == student_id,
        AssignmentStudentWork.status == "graded",
        AssignmentStudentWork.extracted_text == DEMO_UPLOAD_MARKER)).all())
    return StudentLearningOverview(
        student_id=student_id,
        assignment_count=len(submissions),
        average_score=sum(item.total_score for item in submissions) / len(submissions) if submissions else None,
        completion_rate=len(submissions) / assignment_count if assignment_count else 0,
        profiles=[ProfileRead.model_validate(profile) for profile in profiles],
        recent_assignments=[{
            "id": item.assignment_id,
            "title": db.get(Assignment, item.assignment_id).title,
            "assigned_at": db.get(Assignment, item.assignment_id).assigned_at,
            "status": db.get(Assignment, item.assignment_id).status,
            "mode": db.get(Assignment, item.assignment_id).mode,
        } for item in submissions[:4]],
        records=[LearningRecordRead(
            id=record.id,
            assignment_id=record.assignment_id,
            assignment_title=title,
            question_id=record.question_id,
            knowledge_point_id=record.knowledge_point_id,
            knowledge_point_name=point_name,
            is_correct=record.is_correct,
            answer_text=record.student_answer.answer_text,
            score=record.student_answer.score,
            occurred_at=record.occurred_at,
            demo_simulated=record.assignment_id in demo_assignment_ids,
        ) for record, title, point_name in records],
        score_trend=[ScoreTrendPoint(
            assignment_id=item.assignment_id,
            title=db.get(Assignment, item.assignment_id).title,
            assigned_at=db.get(Assignment, item.assignment_id).assigned_at,
            score=item.total_score,
        ) for item in reversed(submissions[:6])],
    )
