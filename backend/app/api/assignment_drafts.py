import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import AssignmentDraft, DraftQuestion, KnowledgePoint, TeachingGoal
from ..schemas.teaching import (AssignmentDraftGenerateRequest, AssignmentDraftRead,
                                DraftQuestionData, DraftQuestionUpdate)
from ..services.ai_service import AIServiceError, get_ai_service
from ..services.teaching_context import build_teaching_context
from ..services.pdf_export import render_pdf
from ..services.word_export import render_docx

router = APIRouter(prefix="/assignment-drafts", tags=["assignment-drafts"])


def get_draft(draft_id: int, db: Session) -> AssignmentDraft:
    draft = db.scalar(
        select(AssignmentDraft).options(selectinload(AssignmentDraft.questions)).where(AssignmentDraft.id == draft_id)
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="作业草稿不存在")
    return draft


def require_editable(draft: AssignmentDraft) -> None:
    if draft.status in ("approved", "published"):
        raise HTTPException(status_code=409, detail="已审核或已发布作业不可直接修改")


def validate_question(question: DraftQuestionData, allowed_ids: set[int]) -> None:
    if question.knowledge_point_id not in allowed_ids:
        raise HTTPException(status_code=422, detail="题目知识点与教学目标不匹配")
    if question.type in ("single_choice", "multiple_choice"):
        if len(question.options) != 4 or len(set(question.options)) != 4:
            raise HTTPException(status_code=422, detail="选择题必须有四个互不重复的选项")
        answers = question.answer_values
        if question.type == "single_choice" and question.answer not in question.options:
            raise HTTPException(status_code=422, detail="单选题答案必须是题目选项")
        if question.type == "multiple_choice" and (len(answers) < 2 or any(item not in question.options for item in answers)):
            raise HTTPException(status_code=422, detail="多选题答案必须是两个以上题目选项")
    elif question.options:
        raise HTTPException(status_code=422, detail="填空题不应包含选择题选项")
    if not question.stem.strip():
        raise HTTPException(status_code=422, detail="题干不能为空")
    if not question.answer.strip():
        raise HTTPException(status_code=422, detail="题目必须有标准答案")


def check_question(question: DraftQuestion, db: Session) -> None:
    point = db.get(KnowledgePoint, question.knowledge_point_id)
    data = DraftQuestionData.model_validate(question)
    result = get_ai_service().review_question(data, point.name)
    question.quality_issues = result.data.issues
    question.quality_status = (
        "needs_revision" if result.data.issues else
        "demo_checked" if result.source == "demo" else "passed"
    )


def validate_generated_questions(questions: list[DraftQuestionData], count: int, allowed: set[int]) -> None:
    if len(questions) != count:
        raise HTTPException(status_code=502, detail="AI返回题量与请求不一致")
    if not any(question.type == "fill_blank" for question in questions):
        raise HTTPException(status_code=502, detail="作业必须包含至少一道填空题")
    if count >= 3 and {question.type for question in questions} != {"single_choice", "multiple_choice", "fill_blank"}:
        raise HTTPException(status_code=502, detail="AI生成的题型不够多样")
    for index, question in enumerate(questions, start=1):
        if question.type in ("single_choice", "multiple_choice") and len(question.options) == 4:
            labels = re.split(r"\s*(?:\|\||[,，、/和])\s*", question.answer.strip().upper())
            if labels and all(re.fullmatch(r"[A-D]", label) for label in labels):
                question.answer = "||".join(question.options[ord(label) - ord("A")] for label in labels)
        try:
            validate_question(question, allowed)
        except HTTPException as exc:
            raise HTTPException(status_code=502, detail=f"第 {index} 题：{exc.detail}") from exc


@router.post("/generate", response_model=AssignmentDraftRead, status_code=201)
def generate_draft(payload: AssignmentDraftGenerateRequest, db: Session = Depends(get_db)) -> AssignmentDraft:
    goal = db.get(TeachingGoal, payload.teaching_goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="教学目标不存在")
    if goal.status != "confirmed":
        raise HTTPException(status_code=409, detail="请先确认教学目标")
    context = build_teaching_context(db, goal) | {
        "topic": goal.topic,
        "knowledge_point_ids": goal.knowledge_point_ids,
        "question_count": payload.question_count,
        "difficulty": payload.difficulty,
    }
    allowed = set(goal.knowledge_point_ids)
    service = get_ai_service()
    for attempt in range(2):
        try:
            result = service.generate_questions(context)
        except AIServiceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            validate_generated_questions(result.data.questions, payload.question_count, allowed)
            break
        except HTTPException as exc:
            if attempt:
                raise HTTPException(status_code=502, detail=f"AI题目校验仍未通过：{exc.detail}。未保存草稿，请重试") from exc
            context = context | {"validation_feedback": exc.detail}
    draft = AssignmentDraft(
        class_id=goal.class_id,
        teaching_goal_id=goal.id,
        title=result.data.title,
        mode="class_unified",
        difficulty=payload.difficulty,
        status="draft",
        source=result.source,
    )
    db.add(draft)
    db.flush()
    for order_no, question in enumerate(result.data.questions, start=1):
        item = DraftQuestion(assignment_draft_id=draft.id, order_no=order_no, **question.model_dump())
        db.add(item)
        db.flush()
        try:
            check_question(item, db)
        except AIServiceError as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    return get_draft(draft.id, db)


@router.get("", response_model=list[AssignmentDraftRead])
def list_drafts(class_id: int, db: Session = Depends(get_db)) -> list[AssignmentDraft]:
    return list(db.scalars(
        select(AssignmentDraft).options(selectinload(AssignmentDraft.questions))
        .where(AssignmentDraft.class_id == class_id)
        .order_by(AssignmentDraft.created_at.desc(), AssignmentDraft.id.desc())
    ).all())


@router.get("/{draft_id}", response_model=AssignmentDraftRead)
def read_draft(draft_id: int, db: Session = Depends(get_db)) -> AssignmentDraft:
    return get_draft(draft_id, db)


@router.get("/{draft_id}/pdf")
def download_draft_pdf(draft_id: int, db: Session = Depends(get_db)) -> Response:
    draft = get_draft(draft_id, db)
    blocks = [("meta", "班级统一作业  |  姓名：____________  班级：____________")]
    if draft.status not in ("approved", "published"):
        blocks.append(("meta", "教师审核前草稿，请核对题目后使用"))
    for question in draft.questions:
        label = {"single_choice": "单选", "multiple_choice": "多选", "fill_blank": "填空"}[question.type]
        blocks.append(("heading", f"{question.order_no}. {label}题"))
        blocks.append(("body", question.stem))
        for index, option in enumerate(question.options):
            blocks.append(("body", f"{chr(65 + index)}. {option}"))
        if question.type == "fill_blank":
            blocks.append(("body", "答：____________________________________________"))
    return Response(render_pdf(draft.title, blocks), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="assignment-{draft_id}.pdf"'})


@router.get("/{draft_id}/docx")
def download_draft_docx(draft_id: int, db: Session = Depends(get_db)) -> Response:
    draft = get_draft(draft_id, db)
    blocks = [("meta", "班级统一作业  |  姓名：____________  班级：____________")]
    if draft.status not in ("approved", "published"):
        blocks.append(("meta", "教师审核前草稿，请核对题目后使用"))
    for question in draft.questions:
        label = {"single_choice": "单选", "multiple_choice": "多选", "fill_blank": "填空"}[question.type]
        blocks.append(("heading", f"{question.order_no}. {label}题"))
        blocks.append(("body", question.stem))
        blocks.extend(("body", f"{chr(65 + index)}. {option}") for index, option in enumerate(question.options))
        if question.type == "fill_blank":
            blocks.append(("body", "答：____________________________________________"))
    return Response(render_docx(draft.title, blocks), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="assignment-{draft_id}.docx"'})


@router.delete("/{draft_id}", status_code=204)
def delete_draft(draft_id: int, db: Session = Depends(get_db)) -> None:
    draft = get_draft(draft_id, db)
    if draft.status in ("approved", "published"):
        raise HTTPException(status_code=409, detail="已审核或已发布作业不能删除")
    db.delete(draft)
    db.commit()


@router.patch("/{draft_id}/questions/{question_id}", response_model=AssignmentDraftRead)
def update_question(draft_id: int, question_id: int, payload: DraftQuestionUpdate, db: Session = Depends(get_db)) -> AssignmentDraft:
    draft = get_draft(draft_id, db)
    require_editable(draft)
    question = next((item for item in draft.questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    values = DraftQuestionData.model_validate(question).model_dump() | payload.model_dump(exclude_unset=True)
    data = DraftQuestionData.model_validate(values)
    goal = db.get(TeachingGoal, draft.teaching_goal_id)
    validate_question(data, set(goal.knowledge_point_ids))
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, key, value)
    question.quality_status = "unchecked"
    question.quality_issues = []
    draft.status = "draft"
    db.commit()
    return get_draft(draft_id, db)


@router.delete("/{draft_id}/questions/{question_id}", response_model=AssignmentDraftRead)
def delete_question(draft_id: int, question_id: int, db: Session = Depends(get_db)) -> AssignmentDraft:
    draft = get_draft(draft_id, db)
    require_editable(draft)
    question = next((item for item in draft.questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if len(draft.questions) <= 1:
        raise HTTPException(status_code=409, detail="作业至少保留一道题")
    db.delete(question)
    draft.status = "draft"
    db.commit()
    db.expire(draft, ["questions"])
    return get_draft(draft_id, db)


@router.post("/{draft_id}/questions/{question_id}/regenerate", response_model=AssignmentDraftRead)
def regenerate_question(draft_id: int, question_id: int, db: Session = Depends(get_db)) -> AssignmentDraft:
    draft = get_draft(draft_id, db)
    require_editable(draft)
    question = next((item for item in draft.questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    goal = db.get(TeachingGoal, draft.teaching_goal_id)
    context = build_teaching_context(db, goal) | {
        "topic": goal.topic,
        "knowledge_point_ids": [question.knowledge_point_id],
        "knowledge_points": [point for point in build_teaching_context(db, goal)["knowledge_points"] if point["knowledge_point_id"] == question.knowledge_point_id],
        "question_count": 1,
        "difficulty": question.difficulty,
    }
    try:
        result = get_ai_service().generate_questions(context)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    replacement = result.data.questions[0]
    validate_question(replacement, {question.knowledge_point_id})
    for key, value in replacement.model_dump().items():
        setattr(question, key, value)
    try:
        check_question(question, db)
    except AIServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    draft.status = "draft"
    db.commit()
    return get_draft(draft_id, db)


@router.post("/{draft_id}/questions/{question_id}/check", response_model=AssignmentDraftRead)
def review_question(draft_id: int, question_id: int, db: Session = Depends(get_db)) -> AssignmentDraft:
    draft = get_draft(draft_id, db)
    require_editable(draft)
    question = next((item for item in draft.questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    try:
        check_question(question, db)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    draft.status = "draft"
    db.commit()
    return get_draft(draft_id, db)


@router.post("/{draft_id}/submit-review", response_model=AssignmentDraftRead)
def submit_review(draft_id: int, db: Session = Depends(get_db)) -> AssignmentDraft:
    draft = get_draft(draft_id, db)
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail="当前作业不能提交审核")
    if not draft.questions or any(item.quality_status not in ("passed", "demo_checked") for item in draft.questions):
        raise HTTPException(status_code=409, detail="请先完成全部题目的质量检查")
    draft.status = "pending_review"
    db.commit()
    return get_draft(draft_id, db)


@router.post("/{draft_id}/approve", response_model=AssignmentDraftRead)
def approve_draft(draft_id: int, db: Session = Depends(get_db)) -> AssignmentDraft:
    draft = get_draft(draft_id, db)
    if draft.status != "pending_review":
        raise HTTPException(status_code=409, detail="请先提交作业审核")
    draft.status = "approved"
    db.commit()
    return get_draft(draft_id, db)
