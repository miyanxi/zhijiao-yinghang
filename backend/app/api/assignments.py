from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (AssessmentImport, Assignment, AssignmentDraft, AssignmentPublication,
                      AssignmentQuestion, Class, LearningRecord, Question,
                      Student, StudentAnswer, StudentSubmission, TargetedTraining)
from ..schemas.assignments import (AssignmentDetailRead, AssignmentQuestionRead,
                                   AssignmentRead, StudentAnswerRead,
                                   StudentSubmissionCreate, SubmissionRead)
from ..services.profile import rebuild_profiles

router = APIRouter(prefix="/assignments", tags=["assignments"])


def _split_multiple(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"\|\||[|,，、/]", value) if item.strip()]


def _normalized_answer(question: Question, value: str) -> str:
    if question.type == "multiple_choice":
        return "||".join(sorted(_split_multiple(value)))
    if question.type == "fill_blank":
        return re.sub(r"\s+", "", value).strip().lower()
    return value.strip()


def _is_valid_answer(question: Question, value: str) -> bool:
    if question.type == "single_choice":
        return value in question.options
    if question.type == "multiple_choice":
        values = _split_multiple(value)
        return len(values) >= 2 and len(set(values)) == len(values) and all(item in question.options for item in values)
    return bool(value.strip())


@router.post("/publish/{draft_id}", response_model=AssignmentRead, status_code=201)
def publish_draft(draft_id: int, db: Session = Depends(get_db)) -> AssignmentRead:
    draft = db.scalar(select(AssignmentDraft).options(selectinload(AssignmentDraft.questions)).where(AssignmentDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="作业草稿不存在")
    if draft.status != "approved" or not draft.questions:
        raise HTTPException(status_code=409, detail="只有教师审核通过的作业才能发布")
    if db.get(AssignmentPublication, draft_id) is not None:
        raise HTTPException(status_code=409, detail="该作业已发布")
    if any(item.quality_status not in ("passed", "demo_checked") for item in draft.questions):
        raise HTTPException(status_code=409, detail="存在未完成质量检查的题目")
    published_at = datetime.utcnow()
    assignment = Assignment(class_id=draft.class_id, title=draft.title, mode="class_unified", status="published", assigned_at=published_at)
    db.add(assignment)
    db.flush()
    total = len(draft.questions)
    for index, item in enumerate(draft.questions):
        question = Question(type=item.type, stem=item.stem, options=item.options, answer=item.answer,
                            explanation=item.explanation, difficulty=item.difficulty, source=draft.source,
                            knowledge_points=[item.knowledge_point])
        db.add(question)
        db.flush()
        score = round(100 / total, 2) if index < total - 1 else round(100 - round(100 / total, 2) * (total - 1), 2)
        db.add(AssignmentQuestion(assignment_id=assignment.id, question_id=question.id, order_no=item.order_no, score=score))
    db.add(AssignmentPublication(assignment_draft_id=draft.id, assignment_id=assignment.id, published_at=published_at))
    draft.status = "published"
    db.commit()
    db.refresh(assignment)
    return _assignment_summary(assignment, db)


@router.post("/{assignment_id}/submissions", response_model=SubmissionRead, status_code=201)
def submit_answers(assignment_id: int, payload: StudentSubmissionCreate, db: Session = Depends(get_db)) -> SubmissionRead:
    assignment = db.scalar(select(Assignment).options(selectinload(Assignment.questions).selectinload(AssignmentQuestion.question).selectinload(Question.knowledge_points)).where(Assignment.id == assignment_id))
    if assignment is None:
        raise HTTPException(status_code=404, detail="作业不存在")
    training = db.scalar(select(TargetedTraining).where(TargetedTraining.assignment_id == assignment_id))
    publication = db.scalar(select(AssignmentPublication.assignment_id).where(AssignmentPublication.assignment_id == assignment_id))
    imported = db.scalar(select(AssessmentImport.id).where(AssessmentImport.assignment_id == assignment_id))
    if assignment.status not in ("published", "analyzed") or (publication is None and training is None and imported is None):
        raise HTTPException(status_code=409, detail="该作业未开放提交")
    student = db.get(Student, payload.student_id)
    if student is None or student.class_id != assignment.class_id or student.status != "在读":
        raise HTTPException(status_code=422, detail="学生不属于当前班级或已停用")
    if training is not None and student.id != training.student_id:
        raise HTTPException(status_code=403, detail="专项训练仅开放给教师确认的目标学生")
    if db.scalar(select(StudentSubmission.id).where(StudentSubmission.assignment_id == assignment_id, StudentSubmission.student_id == student.id)):
        raise HTTPException(status_code=409, detail="该学生已提交过此作业")
    answer_map = {item.question_id: item.answer_text for item in payload.answers}
    expected_ids = {item.question_id for item in assignment.questions}
    if len(answer_map) != len(payload.answers) or set(answer_map) != expected_ids:
        raise HTTPException(status_code=422, detail="必须完整提交本次作业的每道题，且不能重复")
    for item in assignment.questions:
        if not _is_valid_answer(item.question, answer_map[item.question_id]):
            raise HTTPException(status_code=422, detail="答案格式与题型不匹配")
    submitted_at = datetime.utcnow()
    submission = StudentSubmission(assignment_id=assignment.id, student_id=student.id, submitted_at=submitted_at, total_score=0)
    db.add(submission)
    db.flush()
    for item in assignment.questions:
        question = item.question
        correct = _normalized_answer(question, answer_map[question.id]) == _normalized_answer(question, question.answer)
        answer = StudentAnswer(submission_id=submission.id, question_id=question.id,
                               answer_text=answer_map[question.id], is_correct=correct,
                               score=item.score if correct else 0)
        db.add(answer)
        db.flush()
        for point in question.knowledge_points:
            db.add(LearningRecord(student_id=student.id, assignment_id=assignment.id,
                                  question_id=question.id, student_answer_id=answer.id,
                                  knowledge_point_id=point.id, is_correct=correct,
                                  occurred_at=submitted_at))
        submission.total_score += answer.score
    db.flush()
    submitted_count = db.scalar(select(func.count()).select_from(StudentSubmission).where(StudentSubmission.assignment_id == assignment.id)) or 0
    active_count = 1 if training is not None else db.scalar(select(func.count()).select_from(Student).where(Student.class_id == assignment.class_id, Student.status == "在读")) or 0
    if submitted_count >= active_count:
        assignment.status = "analyzed"
        if training is not None:
            training.status = "completed"
    rebuild_profiles(db)
    detail = get_assignment(assignment.id, db)
    return next(item for item in detail.submissions if item.student_id == student.id)


def _assignment_summary(assignment: Assignment, db: Session) -> AssignmentRead:
    submissions = db.scalars(select(StudentSubmission).where(StudentSubmission.assignment_id == assignment.id)).all()
    return AssignmentRead(
        id=assignment.id,
        title=assignment.title,
        assigned_at=assignment.assigned_at,
        status=assignment.status,
        mode=assignment.mode,
        question_count=len(assignment.questions),
        submission_count=len(submissions),
        average_score=sum(item.total_score for item in submissions) / len(submissions) if submissions else None,
        source_draft_id=db.scalar(select(AssignmentPublication.assignment_draft_id).where(AssignmentPublication.assignment_id == assignment.id)),
    )


@router.get("", response_model=list[AssignmentRead])
def list_assignments(class_id: int, db: Session = Depends(get_db)) -> list[AssignmentRead]:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    assignments = db.scalars(
        select(Assignment)
        .options(selectinload(Assignment.questions).selectinload(AssignmentQuestion.question))
        .where(Assignment.class_id == class_id)
        .order_by(Assignment.assigned_at.desc())
    ).all()
    return [_assignment_summary(assignment, db) for assignment in assignments]


@router.get("/{assignment_id}", response_model=AssignmentDetailRead)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)) -> AssignmentDetailRead:
    assignment = db.scalar(
        select(Assignment)
        .options(
            selectinload(Assignment.questions).selectinload(AssignmentQuestion.question).selectinload(Question.knowledge_points),
        )
        .where(Assignment.id == assignment_id)
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="作业不存在")
    submissions = db.scalars(
        select(StudentSubmission)
        .options(selectinload(StudentSubmission.student), selectinload(StudentSubmission.answers).selectinload(StudentAnswer.question).selectinload(Question.knowledge_points)).where(StudentSubmission.assignment_id == assignment_id)
    ).all()
    summary = _assignment_summary(assignment, db)
    questions = [AssignmentQuestionRead(
        question_id=item.question.id,
        order_no=item.order_no,
        type=item.question.type,
        stem=item.question.stem,
        options=item.question.options,
        answer=item.question.answer,
        explanation=item.question.explanation,
        difficulty=item.question.difficulty,
        knowledge_point_names=[point.name for point in item.question.knowledge_points],
    ) for item in assignment.questions]
    submission_reads = []
    for submission in submissions:
        student = submission.student
        answer_reads = [StudentAnswerRead(
            question_id=answer.question_id,
            question_stem=answer.question.stem,
            knowledge_point_names=[point.name for point in answer.question.knowledge_points],
            answer_text=answer.answer_text,
            is_correct=answer.is_correct,
            score=answer.score,
        ) for answer in submission.answers]
        submission_reads.append(SubmissionRead(
            id=submission.id,
            student_id=submission.student_id,
            student_name=student.name,
            submitted_at=submission.submitted_at,
            total_score=submission.total_score,
            answers=answer_reads,
        ))
    return AssignmentDetailRead(**summary.model_dump(), questions=questions, submissions=submission_reads)
