from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AssignmentDraft, Class, KnowledgePoint, LessonPlan, TeachingGoal
from ..schemas.teaching import (GoalCreate, GoalParseRequest, GoalParseResult,
                                GoalRead, GoalUpdate, KnowledgePointCreate)
from ..services.ai_service import AIServiceError, get_ai_service
from ..services.teaching_context import build_class_memory

router = APIRouter(prefix="/teaching-goals", tags=["teaching-goals"])


def validate_points(db: Session, point_ids: list[int]) -> None:
    if not point_ids or len(set(point_ids)) != len(point_ids):
        raise HTTPException(status_code=422, detail="请至少选择一个不重复的知识点")
    found = set(db.scalars(select(KnowledgePoint.id).where(KnowledgePoint.id.in_(point_ids))).all())
    if found != set(point_ids):
        raise HTTPException(status_code=422, detail="包含不存在的知识点")


@router.post("/parse", response_model=GoalParseResult)
def parse_goal(payload: GoalParseRequest, db: Session = Depends(get_db)) -> GoalParseResult:
    classroom = db.get(Class, payload.class_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    points = [dict(id=item.id, name=item.name) for item in db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)).all()]
    memory = build_class_memory(db, payload.class_id, raw_input=payload.raw_input)
    try:
        result = get_ai_service().parse_goal(payload.raw_input, classroom.grade, points, memory)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result.data.knowledge_point_ids:
        validate_points(db, result.data.knowledge_point_ids)
    relevant_memory = build_class_memory(db, payload.class_id, result.data.knowledge_point_ids, payload.raw_input)
    data = result.data.model_copy(update={
        "class_context": result.data.class_context.strip() or relevant_memory["summary"],
        "teaching_advice": relevant_memory["advice"] if result.source == "demo" else result.data.teaching_advice or relevant_memory["advice"],
        "teacher_requirements": relevant_memory["advice"] if result.source == "demo" else result.data.teaching_advice or result.data.teacher_requirements,
    })
    return GoalParseResult(**data.model_dump(), source=result.source)


@router.post("", response_model=GoalRead, status_code=201)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)) -> TeachingGoal:
    if db.get(Class, payload.class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    data = payload.model_dump()
    if data["knowledge_point_ids"]:
        validate_points(db, data["knowledge_point_ids"])
    else:
        topic = data["topic"].strip()
        point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.name == topic))
        if point is None:
            point = KnowledgePoint(name=topic, category="课程内容")
            db.add(point)
            db.flush()
        data["knowledge_point_ids"] = [point.id]
    advice = (data.pop("teaching_advice", None) or data.pop("teacher_requirements", None) or "").strip()
    if not advice:
        raise HTTPException(status_code=422, detail="请填写本节课上课建议")
    data["teacher_requirements"] = advice
    goal = TeachingGoal(**data, status="draft")
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("", response_model=list[GoalRead])
def list_goals(class_id: int, db: Session = Depends(get_db)) -> list[TeachingGoal]:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    return list(db.scalars(select(TeachingGoal).where(TeachingGoal.class_id == class_id).order_by(TeachingGoal.created_at.desc(), TeachingGoal.id.desc())).all())


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(goal_id: int, db: Session = Depends(get_db)) -> TeachingGoal:
    goal = db.get(TeachingGoal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="教学目标不存在")
    return goal


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(goal_id: int, payload: GoalUpdate, db: Session = Depends(get_db)) -> TeachingGoal:
    goal = get_goal(goal_id, db)
    if goal.status != "draft":
        raise HTTPException(status_code=409, detail="已确认目标不可直接修改")
    changes = payload.model_dump(exclude_unset=True)
    if "knowledge_point_ids" in changes and changes["knowledge_point_ids"]:
        validate_points(db, changes["knowledge_point_ids"])
    elif "knowledge_point_ids" in changes:
        changes.pop("knowledge_point_ids")
    advice = changes.pop("teaching_advice", None)
    if advice is not None:
        changes["teacher_requirements"] = advice
    for key, value in changes.items():
        setattr(goal, key, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.post("/{goal_id}/confirm", response_model=GoalRead)
def confirm_goal(goal_id: int, db: Session = Depends(get_db)) -> TeachingGoal:
    goal = get_goal(goal_id, db)
    if goal.status != "draft":
        raise HTTPException(status_code=409, detail="教学目标已经确认")
    goal.status = "confirmed"
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db: Session = Depends(get_db)) -> None:
    goal = get_goal(goal_id, db)
    if db.scalar(select(LessonPlan.id).where(LessonPlan.teaching_goal_id == goal_id)) or db.scalar(select(AssignmentDraft.id).where(AssignmentDraft.teaching_goal_id == goal_id)):
        raise HTTPException(status_code=409, detail="该目标已经生成教案或作业，暂不能删除；请先保留历史记录")
    db.delete(goal)
    db.commit()


@router.get("/knowledge-points/catalog", response_model=list[dict])
def list_knowledge_points(db: Session = Depends(get_db)) -> list[dict]:
    return [dict(id=item.id, name=item.name, category=item.category) for item in db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)).all()]


@router.post("/knowledge-points", response_model=dict, status_code=201)
def create_knowledge_point(payload: KnowledgePointCreate, db: Session = Depends(get_db)) -> dict:
    name = payload.name.strip()
    category = payload.category.strip()
    if db.scalar(select(KnowledgePoint.id).where(KnowledgePoint.name == name)):
        raise HTTPException(status_code=409, detail="该知识点已经存在")
    point = KnowledgePoint(name=name, category=category)
    db.add(point)
    db.commit()
    db.refresh(point)
    return dict(id=point.id, name=point.name, category=point.category)
