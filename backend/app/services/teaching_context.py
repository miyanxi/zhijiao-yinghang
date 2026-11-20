from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Assignment, KnowledgePoint, LearningRecord, LessonPlanReview,
                      Student, StudentKnowledgeProfile, TeachingGoal)


def build_class_memory(db: Session, class_id: int, point_ids: list[int] | None = None, raw_input: str = "") -> dict:
    """Turn stored learning history into concise, lesson-relevant teacher context."""
    points = list(db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)).all())
    selected = set(point_ids if point_ids is not None else [point.id for point in points])
    records = db.scalars(
        select(LearningRecord)
        .join(Student, Student.id == LearningRecord.student_id)
        .join(Assignment, Assignment.id == LearningRecord.assignment_id)
        .where(Student.class_id == class_id, Assignment.mode == "class_unified")
    ).all()
    by_point = defaultdict(list)
    for record in records:
        if record.knowledge_point_id in selected:
            by_point[record.knowledge_point_id].append(record.is_correct)
    point_map = {point.id: point for point in points}
    observations = []
    advice = []
    for point_id in sorted(selected):
        point = point_map.get(point_id)
        values = by_point.get(point_id, [])
        if point is None or not values:
            continue
        accuracy = sum(values) / len(values)
        if accuracy < 0.7:
            observations.append(f"{point.name}是班级近期较集中的易错点")
            advice.append(f"讲解{point.name}时先用典型错误引入，再安排分层练习")
        elif accuracy < 0.8:
            observations.append(f"{point.name}的掌握情况仍有波动")
            advice.append(f"{point.name}建议保留一个针对性辨析环节")
        else:
            observations.append(f"{point.name}整体掌握相对稳定")
    focus = db.execute(
        select(Student.name, KnowledgePoint.name)
        .join(StudentKnowledgeProfile, StudentKnowledgeProfile.student_id == Student.id)
        .join(KnowledgePoint, KnowledgePoint.id == StudentKnowledgeProfile.knowledge_point_id)
        .where(Student.class_id == class_id,
               StudentKnowledgeProfile.knowledge_point_id.in_(selected),
               StudentKnowledgeProfile.attention_status == "重点关注")
        .order_by(StudentKnowledgeProfile.recent_accuracy)
        .limit(4)
    ).all()
    if focus:
        names = "、".join(f"{name}（{point}）" for name, point in focus)
        observations.append(f"少数学生仍需要教师在课堂中重点追问：{names}")
        advice.append("课堂练习后请教师快速查看少数学生的解题理由")
    reviews = db.execute(
        select(LessonPlanReview.evaluation, LessonPlanReview.reflection)
        .join(LessonPlanReview.lesson_plan)
        .where(LessonPlanReview.lesson_plan.has(class_id=class_id))
        .order_by(LessonPlanReview.updated_at.desc())
        .limit(2)
    ).all()
    if reviews:
        observations.append("系统已保留此前课后复盘，可作为本节课调整节奏的参考")
    if any(word in raw_input for word in ("作文", "写作")) and not any("作文" in item for item in observations):
        observations.append("当前系统暂无作文文本批改记录；相关语法错误只能依据已有语法作业记录判断")
        advice.append("作文课建议补充一段时态自检和同伴互评，课后再沉淀作文错误记录")
    summary = "；".join(observations) if observations else "当前没有与本节课直接相关的历史学情记录。"
    recommendation = "；".join(advice) if advice else "建议围绕本节课目标安排示例、练习和课堂反馈。"
    return {
        "summary": summary,
        "advice": recommendation,
        "observations": observations,
        "recommendations": advice,
        "focus_students": [{"name": name, "knowledge_point": point} for name, point in focus],
    }


def build_teaching_context(db: Session, goal: TeachingGoal) -> dict:
    point_ids = goal.knowledge_point_ids
    points = db.scalars(select(KnowledgePoint).where(KnowledgePoint.id.in_(point_ids))).all()
    records = db.scalars(
        select(LearningRecord)
        .join(Student, Student.id == LearningRecord.student_id)
        .where(Student.class_id == goal.class_id, LearningRecord.knowledge_point_id.in_(point_ids))
    ).all()
    by_point = defaultdict(list)
    for record in records:
        by_point[record.knowledge_point_id].append(record.is_correct)
    class_summary = [
        {"knowledge_point_id": point.id, "name": point.name,
         "attempts": len(by_point[point.id]),
         "accuracy": sum(by_point[point.id]) / len(by_point[point.id]) if by_point[point.id] else None}
        for point in points
    ]
    attention = db.execute(
        select(Student.name, KnowledgePoint.name, StudentKnowledgeProfile.recent_accuracy)
        .join(StudentKnowledgeProfile, StudentKnowledgeProfile.student_id == Student.id)
        .join(KnowledgePoint, KnowledgePoint.id == StudentKnowledgeProfile.knowledge_point_id)
        .where(Student.class_id == goal.class_id,
               StudentKnowledgeProfile.knowledge_point_id.in_(point_ids),
               StudentKnowledgeProfile.attention_status == "重点关注")
        .limit(5)
    ).all()
    memory = build_class_memory(db, goal.class_id, point_ids)
    return {
        "goal": {
            "topic": goal.topic,
            "objectives": goal.objectives,
            "key_points": goal.key_points,
            "difficult_points": goal.difficult_points,
            "class_context": goal.class_context,
            "teacher_requirements": goal.teacher_requirements,
            "teaching_advice": goal.teacher_requirements,
        },
        "knowledge_points": class_summary,
        "attention_students": [
            {"name": name, "knowledge_point": point_name, "recent_accuracy": accuracy}
            for name, point_name, accuracy in attention
        ],
        "class_memory": memory,
        "learning_analysis": memory["summary"],
        "teaching_advice": memory["advice"],
    }
