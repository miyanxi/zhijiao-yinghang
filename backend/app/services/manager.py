from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Class, KnowledgePoint, Student, TeachingGoal
from ..schemas.manager import (ManagerAction, ManagerMetric, ManagerRequest,
                               ManagerResponse)
from .ai_service import get_ai_service
from .learning_queries import class_learning_overview, student_learning_overview
from .name_matching import matched_names
from .training_queries import training_candidates


def _percent(value: float | None) -> str:
    return "--" if value is None else f"{value * 100:.1f}%"


def _score(value: float | None) -> str:
    return "--" if value is None else f"{value:.1f} 分"


def _response(intent: str, source: str, title: str, summary: str,
              metrics: list[ManagerMetric] | None = None,
              evidence: list[str] | None = None,
              action: ManagerAction | None = None) -> ManagerResponse:
    return ManagerResponse(intent=intent, source=source, title=title, summary=summary,
                           metrics=metrics or [], evidence=evidence or [], action=action)


def handle_manager_request(payload: ManagerRequest, db: Session) -> ManagerResponse:
    classroom = db.get(Class, payload.class_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="请输入教学请求")
    if any(word in message.lower() for word in ("删除", "发布", "绕过", "sql", "修改分数", "改成绩", "自动确认", "自动决定")):
        return _response("unsupported", "program", "需要教师操作", "发布、删除和更改已确认数据不能通过总管家执行。请在对应工作台审核并操作。")

    students = db.scalars(select(Student).where(Student.class_id == classroom.id, Student.status == "在读")).all()
    points = db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)).all()
    service = get_ai_service()
    recognized = service.understand_manager_request(message, [item.name for item in students], [item.name for item in points])
    data = recognized.data
    source = recognized.source
    if data.intent == "unsupported":
        return _response("unsupported", source, "暂不能处理", "请提出班级或学生学情查询、教案准备、班级统一作业准备，或针对持续性问题的专项训练准备请求。")

    if data.intent in ("student_analysis", "targeted_training"):
        student_names = matched_names(message, [student.name for student in students])
        mentions = [student for student in students if student.name in student_names]
        if len(mentions) != 1 or data.student_name != mentions[0].name:
            return _response(data.intent, "program", "请明确学生", "请使用当前班级中一名在读学生的完整姓名，一次只指定一人。")
        if data.student_name not in {student.name for student in students}:
            return _response(data.intent, "program", "请明确学生", "当前班级中未匹配到这名在读学生，请使用学生管理中的姓名。")
        matches = [student for student in students if student.name == data.student_name]
        if len(matches) != 1:
            return _response(data.intent, "program", "请明确学生", "当前班级存在同名学生，请先在学生管理中核对。")
        student = matches[0]

        if data.intent == "student_analysis":
            overview = student_learning_overview(student.id, db)
            focus = [item for item in overview.profiles if item.attention_status == "重点关注"]
            metrics = [
                ManagerMetric(label="历史平均分", value=_score(overview.average_score)),
                ManagerMetric(label="统一作业完成率", value=_percent(overview.completion_rate)),
                ManagerMetric(label="重点知识点", value=f"{len(focus)} 项"),
            ]
            evidence = [f"{item.knowledge_point.name}：累计正确率 {_percent(item.accuracy)}，近期 {_percent(item.recent_accuracy)}，连续薄弱 {item.consecutive_weak_count} 次。" for item in focus[:3]]
            evidence.extend(f"近期错题：{item.assignment_title} / {item.knowledge_point_name}。" for item in overview.records if not item.is_correct and len(evidence) < 5)
            fallback = f"{student.name}当前有 {len(focus)} 项重点关注知识点；请结合逐题记录判断后续教学安排。"
            summary = service.summarize_manager_evidence(f"{student.name}学习情况", [item.model_dump() for item in metrics], evidence, fallback)
            return _response(data.intent, summary.source, f"{student.name}学习情况", summary.data.summary,
                             metrics, evidence, ManagerAction(view="student-detail", label="查看学生画像", student_id=student.id))

        candidates = [item for item in training_candidates(classroom.id, db) if item.student_id == student.id]
        if not candidates:
            return _response(data.intent, "program", "暂不符合专项训练规则", f"{student.name}目前没有被程序标记为持续性问题的知识点。教师仍可查看其学习画像，但系统不会默认生成个体作业。",
                             action=ManagerAction(view="student-detail", label="查看学生画像", student_id=student.id))
        point_names = matched_names(message, [point.name for point in points])
        point_mentions = [point for point in points if point.name in point_names]
        if len(point_mentions) > 1:
            return _response(data.intent, "program", "请明确知识点", "请求中提到多个知识点，请一次指定一项专项训练。")
        if data.knowledge_point_name:
            if data.knowledge_point_name not in {point.name for point in point_mentions}:
                return _response(data.intent, "program", "请核对知识点", "识别到的知识点与教师原话不一致，请明确指定知识点。")
            candidate = next((item for item in candidates if item.knowledge_point_name == data.knowledge_point_name), None)
        elif len(candidates) == 1:
            candidate = candidates[0]
        else:
            candidate = None
        if candidate is None:
            names = "、".join(item.knowledge_point_name for item in candidates)
            return _response(data.intent, "program", "请明确知识点", f"{student.name}当前可供教师核对的重点知识点：{names}。请指定其中一项。")
        duration = data.duration_minutes or 15
        count = data.question_count or 10
        if not 5 <= duration <= 60 or not 3 <= count <= 20:
            return _response(data.intent, "program", "训练参数不合法", "训练时长须为 5–60 分钟，题量须为 3–20 题。")
        metrics = [
            ManagerMetric(label="近期正确率", value=_percent(candidate.recent_accuracy)),
            ManagerMetric(label="连续薄弱", value=f"{candidate.consecutive_weak_count} 次"),
            ManagerMetric(label="训练设置", value=f"{count} 题 / {duration} 分钟"),
        ]
        evidence = [f"{candidate.knowledge_point_name}：{candidate.total_attempts} 次逐题记录，累计正确率 {_percent(candidate.accuracy)}。"]
        return _response(data.intent, source, f"{student.name} · {candidate.knowledge_point_name}",
                         "程序画像满足重点关注规则。请进入专项训练工作台核对并由教师确认对象，之后才能生成草稿。",
                         metrics, evidence, ManagerAction(view="training", label="核对专项训练候选", requires_confirmation=True,
                             student_id=student.id, knowledge_point_id=candidate.knowledge_point_id,
                             duration_minutes=duration, question_count=count))

    if data.intent == "class_analysis":
        overview = class_learning_overview(classroom.id, db)
        metrics = [
            ManagerMetric(label="班级平均分", value=_score(overview.average_score)),
            ManagerMetric(label="统一作业完成率", value=_percent(overview.completion_rate)),
            ManagerMetric(label="待关注学生", value=f"{overview.attention_students} 人"),
            ManagerMetric(label="累计错题", value=f"{overview.error_count} 题"),
        ]
        evidence = [f"{item.name}：{item.attempts} 次作答，正确率 {_percent(item.accuracy)}。" for item in overview.knowledge_points[:3]]
        fallback = f"{classroom.name}已记录 {overview.assignment_count} 次统一作业；班级平均分 {_score(overview.average_score)}，请查看知识点明细。"
        summary = service.summarize_manager_evidence(f"{classroom.name}学情", [item.model_dump() for item in metrics], evidence, fallback)
        return _response(data.intent, summary.source, f"{classroom.name}学情", summary.data.summary,
                         metrics, evidence, ManagerAction(view="analytics", label="查看班级学情"))

    goals = db.scalars(select(TeachingGoal).where(
        TeachingGoal.class_id == classroom.id, TeachingGoal.status == "confirmed"
    ).order_by(TeachingGoal.created_at.desc(), TeachingGoal.id.desc())).all()
    if not goals:
        return _response(data.intent, "program", "先确认教学目标", "当前班级没有已确认的教学目标。请先由教师录入并确认，再准备教案或统一作业。",
                         action=ManagerAction(view="goals", label="前往教学目标"))
    if data.intent == "lesson_prep":
        return _response(data.intent, source, "教案准备", f"当前班级有 {len(goals)} 个已确认教学目标。请在智能教案工作台选择目标、检查学情并生成草稿；教师逐模块审核。",
                         [ManagerMetric(label="已确认目标", value=f"{len(goals)} 个")],
                         [f"最近确认目标：{goals[0].topic}。"],
                         ManagerAction(view="lesson-plans", label="前往智能教案", requires_confirmation=True))
    return _response(data.intent, source, "班级统一作业准备", f"当前班级有 {len(goals)} 个已确认教学目标。请在智能作业工作台选择目标并生成全班统一草稿，核对题目后由教师审核发布。",
                     [ManagerMetric(label="已确认目标", value=f"{len(goals)} 个")],
                     [f"最近确认目标：{goals[0].topic}。"],
                     ManagerAction(view="smart-assignments", label="前往智能作业", requires_confirmation=True))
