from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import LessonPlan, LessonPlanReview, TeachingGoal
from ..schemas.teaching import (LessonPlanGenerateRequest, LessonPlanRead,
                                LessonPlanReviewUpdate, LessonPlanUpdate,
                                LessonSectionUpdate)
from ..services.ai_service import AIServiceError, LESSON_SECTIONS, get_ai_service
from ..services.teaching_context import build_teaching_context
from ..services.pdf_export import render_pdf
from ..services.word_export import render_docx

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])


def get_plan(plan_id: int, db: Session) -> LessonPlan:
    plan = db.scalar(select(LessonPlan).options(selectinload(LessonPlan.post_review)).where(LessonPlan.id == plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="教案不存在")
    return plan


def require_editable(plan: LessonPlan) -> None:
    if plan.status == "approved":
        raise HTTPException(status_code=409, detail="已审核教案不可直接修改")


@router.post("/generate", response_model=LessonPlanRead, status_code=201)
def generate_plan(payload: LessonPlanGenerateRequest, db: Session = Depends(get_db)) -> LessonPlan:
    goal = db.get(TeachingGoal, payload.teaching_goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="教学目标不存在")
    if goal.status != "confirmed":
        raise HTTPException(status_code=409, detail="请先确认教学目标")
    context = build_teaching_context(db, goal) | {
        "difficulty": payload.difficulty,
        "duration_minutes": payload.duration_minutes,
    }
    try:
        result = get_ai_service().generate_lesson(context)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    sections = [section.model_dump() for section in result.data.sections]
    keys = [section["key"] for section in sections]
    if len(keys) != len(set(keys)) or set(keys) != {key for key, _ in LESSON_SECTIONS}:
        raise HTTPException(status_code=502, detail="AI教案模块不完整，请重新生成")
    plan = LessonPlan(
        class_id=goal.class_id,
        teaching_goal_id=goal.id,
        title=result.data.title,
        sections=sections,
        difficulty=payload.difficulty,
        duration_minutes=payload.duration_minutes,
        status="draft",
        source=result.source,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("", response_model=list[LessonPlanRead])
def list_plans(class_id: int, db: Session = Depends(get_db)) -> list[LessonPlan]:
    return list(db.scalars(select(LessonPlan).options(selectinload(LessonPlan.post_review)).where(LessonPlan.class_id == class_id).order_by(LessonPlan.created_at.desc(), LessonPlan.id.desc())).all())


@router.get("/{plan_id}", response_model=LessonPlanRead)
def read_plan(plan_id: int, db: Session = Depends(get_db)) -> LessonPlan:
    return get_plan(plan_id, db)


@router.get("/{plan_id}/pdf")
def download_plan_pdf(plan_id: int, db: Session = Depends(get_db)) -> Response:
    plan = get_plan(plan_id, db)
    blocks = [("meta", f"难度：{plan.difficulty}  |  课堂时间：{plan.duration_minutes}分钟")]
    for section in plan.sections:
        if section["key"] in ("evaluation", "reflection"):
            continue
        blocks.extend([("heading", section["title"]), ("body", section["content"])])
    if plan.post_review:
        blocks.extend([("heading", "课堂评价"), ("body", plan.post_review.evaluation),
                       ("heading", "教学反思"), ("body", plan.post_review.reflection)])
    return Response(render_pdf(plan.title, blocks), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="lesson-plan-{plan_id}.pdf"'})


@router.get("/{plan_id}/docx")
def download_plan_docx(plan_id: int, db: Session = Depends(get_db)) -> Response:
    plan = get_plan(plan_id, db)
    blocks = [("meta", f"难度：{plan.difficulty}  |  课堂时间：{plan.duration_minutes}分钟")]
    for section in plan.sections:
        if section["key"] in ("evaluation", "reflection"):
            continue
        blocks.extend([("heading", section["title"]), ("body", section["content"])])
    if plan.post_review:
        blocks.extend([("heading", "课堂评价"), ("body", plan.post_review.evaluation),
                       ("heading", "教学反思"), ("body", plan.post_review.reflection)])
    return Response(render_docx(plan.title, blocks), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="lesson-plan-{plan_id}.docx"'})


@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db)) -> None:
    plan = get_plan(plan_id, db)
    if plan.status == "approved":
        raise HTTPException(status_code=409, detail="已审核教案不能删除")
    db.delete(plan)
    db.commit()


@router.patch("/{plan_id}", response_model=LessonPlanRead)
def update_plan(plan_id: int, payload: LessonPlanUpdate, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    require_editable(plan)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    plan.status = "draft"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}/sections/{section_key}", response_model=LessonPlanRead)
def update_section(plan_id: int, section_key: str, payload: LessonSectionUpdate, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    require_editable(plan)
    sections = [dict(section) for section in plan.sections]
    match = next((section for section in sections if section["key"] == section_key), None)
    if match is None:
        raise HTTPException(status_code=404, detail="教案模块不存在")
    match.update(payload.model_dump())
    plan.sections = sections
    plan.status = "draft"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}/sections/{section_key}", response_model=LessonPlanRead)
def delete_section(plan_id: int, section_key: str, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    require_editable(plan)
    sections = [section for section in plan.sections if section["key"] != section_key]
    if len(sections) == len(plan.sections):
        raise HTTPException(status_code=404, detail="教案模块不存在")
    if not sections:
        raise HTTPException(status_code=409, detail="教案至少保留一个模块")
    plan.sections = sections
    plan.status = "draft"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/sections/{section_key}/regenerate", response_model=LessonPlanRead)
def regenerate_section(plan_id: int, section_key: str, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    require_editable(plan)
    current = next((section for section in plan.sections if section["key"] == section_key), None)
    if current is None:
        raise HTTPException(status_code=404, detail="教案模块不存在")
    goal = db.get(TeachingGoal, plan.teaching_goal_id)
    context = build_teaching_context(db, goal) | {
        "topic": goal.topic, "difficulty": plan.difficulty,
        "duration_minutes": current["duration_minutes"],
        "previous_content": current["content"],
    }
    try:
        result = get_ai_service().regenerate_section(context, section_key)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result.data.key != section_key:
        raise HTTPException(status_code=502, detail="AI返回了不匹配的教案模块")
    if result.data.content.strip() == current["content"].strip():
        raise HTTPException(status_code=502, detail="重新生成的内容与原文相同，请重试")
    plan.sections = [result.data.model_dump() if section["key"] == section_key else section for section in plan.sections]
    plan.status = "draft"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/submit-review", response_model=LessonPlanRead)
def submit_review(plan_id: int, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    if plan.status != "draft":
        raise HTTPException(status_code=409, detail="当前教案不能提交审核")
    plan.status = "pending_review"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/approve", response_model=LessonPlanRead)
def approve_plan(plan_id: int, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    if plan.status != "pending_review":
        raise HTTPException(status_code=409, detail="请先提交教案审核")
    plan.status = "approved"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/{plan_id}/post-review", response_model=LessonPlanRead)
def save_post_review(plan_id: int, payload: LessonPlanReviewUpdate, db: Session = Depends(get_db)) -> LessonPlan:
    plan = get_plan(plan_id, db)
    if plan.status != "approved":
        raise HTTPException(status_code=409, detail="请先完成教案审核，再记录课后评价与反思")
    review = db.scalar(select(LessonPlanReview).where(LessonPlanReview.lesson_plan_id == plan_id))
    if review is None:
        review = LessonPlanReview(lesson_plan_id=plan_id, evaluation=payload.evaluation, reflection=payload.reflection)
        db.add(review)
    else:
        review.evaluation = payload.evaluation
        review.reflection = payload.reflection
        review.updated_at = datetime.utcnow()
    db.commit()
    return get_plan(plan_id, db)
