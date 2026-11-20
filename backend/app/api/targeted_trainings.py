from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (Assignment, AssignmentQuestion, Class, KnowledgePoint,
                      LearningRecord, Question, Student, StudentKnowledgeProfile,
                      StudentSubmission, TargetedTraining)
from ..schemas.teaching import DraftQuestionData
from ..schemas.training import (ConfirmTrainingRequest, TrainingCandidate,
                                TrainingQuestionUpdate, TrainingRead)
from ..services.ai_service import AIServiceError, get_ai_service
from ..services.training_queries import training_candidates

router = APIRouter(prefix="/targeted-trainings", tags=["targeted-trainings"])


def load_training(training_id: int, db: Session) -> TargetedTraining:
    training = db.scalar(select(TargetedTraining).options(
        selectinload(TargetedTraining.student), selectinload(TargetedTraining.knowledge_point)
    ).where(TargetedTraining.id == training_id))
    if training is None:
        raise HTTPException(status_code=404, detail="专项训练不存在")
    return training


def read_training(training: TargetedTraining, db: Session) -> TrainingRead:
    profile = db.scalar(select(StudentKnowledgeProfile).where(
        StudentKnowledgeProfile.student_id == training.student_id,
        StudentKnowledgeProfile.knowledge_point_id == training.knowledge_point_id,
    ))
    submission = db.scalar(select(StudentSubmission).where(
        StudentSubmission.assignment_id == training.assignment_id,
        StudentSubmission.student_id == training.student_id,
    )) if training.assignment_id else None
    correct_count = 0
    answer_count = 0
    if submission is not None:
        correct_count = sum(answer.is_correct for answer in submission.answers)
        answer_count = len(submission.answers)
    return TrainingRead(
        id=training.id, class_id=training.class_id, student_id=training.student_id,
        student_name=training.student.name, knowledge_point_id=training.knowledge_point_id,
        knowledge_point_name=training.knowledge_point.name, assignment_id=training.assignment_id,
        status=training.status, source=training.source,
        question_count=training.question_count, duration_minutes=training.duration_minutes,
        baseline_accuracy=training.baseline_accuracy,
        baseline_recent_accuracy=training.baseline_recent_accuracy,
        current_accuracy=profile.accuracy if profile else None,
        current_recent_accuracy=profile.recent_accuracy if profile else None,
        training_score=submission.total_score if submission else None,
        training_accuracy=correct_count / answer_count if answer_count else None,
        questions=training.questions, created_at=training.created_at,
    )


@router.get("/candidates", response_model=list[TrainingCandidate])
def list_candidates(class_id: int, db: Session = Depends(get_db)) -> list[TrainingCandidate]:
    return training_candidates(class_id, db)


@router.get("", response_model=list[TrainingRead])
def list_trainings(class_id: int, db: Session = Depends(get_db)) -> list[TrainingRead]:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    trainings = db.scalars(select(TargetedTraining).options(
        selectinload(TargetedTraining.student), selectinload(TargetedTraining.knowledge_point)
    ).where(TargetedTraining.class_id == class_id).order_by(TargetedTraining.id.desc())).all()
    return [read_training(item, db) for item in trainings]


@router.get("/{training_id}", response_model=TrainingRead)
def get_training(training_id: int, db: Session = Depends(get_db)) -> TrainingRead:
    return read_training(load_training(training_id, db), db)


@router.post("/confirm", response_model=TrainingRead, status_code=201)
def confirm_candidate(payload: ConfirmTrainingRequest, db: Session = Depends(get_db)) -> TrainingRead:
    student = db.get(Student, payload.student_id)
    if student is None or student.status != "在读":
        raise HTTPException(status_code=404, detail="在读学生不存在")
    profile = db.scalar(select(StudentKnowledgeProfile).where(
        StudentKnowledgeProfile.student_id == student.id,
        StudentKnowledgeProfile.knowledge_point_id == payload.knowledge_point_id,
    ))
    if profile is None or profile.attention_status != "重点关注":
        raise HTTPException(status_code=409, detail="该学生知识点未达到持续性问题关注规则")
    existing = db.scalar(select(TargetedTraining.id).where(
        TargetedTraining.student_id == student.id,
        TargetedTraining.knowledge_point_id == payload.knowledge_point_id,
        TargetedTraining.status != "completed",
    ))
    if existing:
        raise HTTPException(status_code=409, detail="该学生已有进行中的同知识点专项训练")
    training = TargetedTraining(
        class_id=student.class_id, student_id=student.id,
        knowledge_point_id=payload.knowledge_point_id,
        question_count=payload.question_count, duration_minutes=payload.duration_minutes,
        baseline_accuracy=profile.accuracy,
        baseline_recent_accuracy=profile.recent_accuracy,
        status="confirmed", questions=[],
    )
    db.add(training)
    db.commit()
    return read_training(load_training(training.id, db), db)


@router.post("/{training_id}/generate", response_model=TrainingRead)
def generate_training(training_id: int, db: Session = Depends(get_db)) -> TrainingRead:
    training = load_training(training_id, db)
    if training.status != "confirmed":
        raise HTTPException(status_code=409, detail="请先由教师确认训练对象")
    profile = db.scalar(select(StudentKnowledgeProfile).where(
        StudentKnowledgeProfile.student_id == training.student_id,
        StudentKnowledgeProfile.knowledge_point_id == training.knowledge_point_id,
    ))
    records = db.scalars(select(LearningRecord).where(
        LearningRecord.student_id == training.student_id,
        LearningRecord.knowledge_point_id == training.knowledge_point_id,
        LearningRecord.is_correct.is_(False),
    ).order_by(LearningRecord.occurred_at.desc()).limit(5)).all()
    context = {
        "student_name": training.student.name,
        "topic": training.knowledge_point.name,
        "knowledge_point_ids": [training.knowledge_point_id],
        "knowledge_points": [{"knowledge_point_id": training.knowledge_point_id,
                              "name": training.knowledge_point.name,
                              "accuracy": profile.accuracy if profile else training.baseline_accuracy}],
        "recent_accuracy": profile.recent_accuracy if profile else training.baseline_recent_accuracy,
        "historical_errors": [{
            "stem": record.student_answer.question.stem,
            "student_answer": record.student_answer.answer_text,
            "correct_answer": record.student_answer.question.answer,
            "explanation": record.student_answer.question.explanation,
        } for record in records],
        "question_count": training.question_count,
        "duration_minutes": training.duration_minutes,
        "difficulty": "基础",
    }
    service = get_ai_service()
    try:
        generated = service.generate_targeted_training(context)
        if len(generated.data.questions) != training.question_count:
            raise HTTPException(status_code=502, detail="AI返回题量与要求不一致")
        questions = []
        for order_no, question in enumerate(generated.data.questions, start=1):
            if question.knowledge_point_id != training.knowledge_point_id or len(set(question.options)) != 4 or question.answer not in question.options:
                raise HTTPException(status_code=502, detail="生成题目的知识点、选项或答案不合法")
            review = service.review_question(question, training.knowledge_point.name)
            questions.append(question.model_dump() | {
                "order_no": order_no,
                "quality_status": "needs_revision" if review.data.issues else "demo_checked" if review.source == "demo" else "passed",
                "quality_issues": review.data.issues,
            })
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    training.questions = questions
    training.source = generated.source
    training.status = "draft"
    db.commit()
    return read_training(training, db)


def editable_question(training: TargetedTraining, order_no: int) -> tuple[list[dict], dict]:
    if training.status not in ("draft", "pending_review"):
        raise HTTPException(status_code=409, detail="当前训练题目不可编辑")
    questions = [dict(item) for item in training.questions]
    question = next((item for item in questions if item["order_no"] == order_no), None)
    if question is None:
        raise HTTPException(status_code=404, detail="训练题目不存在")
    return questions, question


@router.patch("/{training_id}/questions/{order_no}", response_model=TrainingRead)
def update_question(training_id: int, order_no: int, payload: TrainingQuestionUpdate, db: Session = Depends(get_db)) -> TrainingRead:
    training = load_training(training_id, db)
    questions, question = editable_question(training, order_no)
    values = payload.model_dump() | {"type": "single_choice", "knowledge_point_id": training.knowledge_point_id}
    DraftQuestionData.model_validate(values)
    if len(set(payload.options)) != 4 or payload.answer not in payload.options:
        raise HTTPException(status_code=422, detail="题目选项或答案不合法")
    question.update(payload.model_dump() | {"quality_status": "unchecked", "quality_issues": []})
    training.questions = questions
    training.status = "draft"
    db.commit()
    return read_training(training, db)


@router.post("/{training_id}/questions/{order_no}/check", response_model=TrainingRead)
def check_question(training_id: int, order_no: int, db: Session = Depends(get_db)) -> TrainingRead:
    training = load_training(training_id, db)
    questions, question = editable_question(training, order_no)
    data = DraftQuestionData.model_validate(question)
    try:
        review = get_ai_service().review_question(data, training.knowledge_point.name)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    question["quality_issues"] = review.data.issues
    question["quality_status"] = "needs_revision" if review.data.issues else "demo_checked" if review.source == "demo" else "passed"
    training.questions = questions
    training.status = "draft"
    db.commit()
    return read_training(training, db)


@router.post("/{training_id}/submit-review", response_model=TrainingRead)
def submit_review(training_id: int, db: Session = Depends(get_db)) -> TrainingRead:
    training = load_training(training_id, db)
    if training.status != "draft" or not training.questions:
        raise HTTPException(status_code=409, detail="当前专项训练不能提交审核")
    if any(item["quality_status"] not in ("passed", "demo_checked") for item in training.questions):
        raise HTTPException(status_code=409, detail="请先检查全部训练题目")
    training.status = "pending_review"
    db.commit()
    return read_training(training, db)


@router.post("/{training_id}/approve", response_model=TrainingRead)
def approve_training(training_id: int, db: Session = Depends(get_db)) -> TrainingRead:
    training = load_training(training_id, db)
    if training.status != "pending_review":
        raise HTTPException(status_code=409, detail="请先提交专项训练供教师审核")
    training.status = "approved"
    db.commit()
    return read_training(training, db)


@router.post("/{training_id}/publish", response_model=TrainingRead)
def publish_training(training_id: int, db: Session = Depends(get_db)) -> TrainingRead:
    training = load_training(training_id, db)
    if training.status != "approved" or not training.questions:
        raise HTTPException(status_code=409, detail="只有教师审核通过的专项训练才能发布")
    assignment = Assignment(class_id=training.class_id, title=f"{training.student.name} · {training.knowledge_point.name}专项训练",
                            mode="targeted_training", status="published", assigned_at=datetime.utcnow())
    db.add(assignment)
    db.flush()
    total = len(training.questions)
    for index, item in enumerate(training.questions):
        question = Question(type=item["type"], stem=item["stem"], options=item["options"],
                            answer=item["answer"], explanation=item["explanation"],
                            difficulty=item["difficulty"], source=training.source or "demo",
                            knowledge_points=[training.knowledge_point])
        db.add(question)
        db.flush()
        score = round(100 / total, 2) if index < total - 1 else round(100 - round(100 / total, 2) * (total - 1), 2)
        db.add(AssignmentQuestion(assignment_id=assignment.id, question_id=question.id,
                                  order_no=item["order_no"], score=score))
    training.assignment_id = assignment.id
    training.status = "published"
    db.commit()
    return read_training(training, db)
