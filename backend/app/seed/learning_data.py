from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Assignment, AssignmentQuestion, Class, KnowledgePoint,
                      LearningRecord, Question, Student, StudentAnswer, StudentSubmission)
from ..services.profile import rebuild_profiles


POINTS = [
    ("谓语动词", "语法"),
    ("一般过去时", "语法"),
    ("非谓语动词", "语法"),
    ("阅读理解", "阅读"),
    ("时态综合运用", "语法"),
    ("写作表达", "写作"),
    ("词汇与语境", "词汇"),
    ("完形填空", "阅读"),
    ("听力理解", "听力"),
    ("句型转换", "语法"),
]

QUESTION_TEMPLATES = [
    ("谓语动词", "She ___ to school every day.", ["go", "goes", "went", "going"], "goes", "主语为第三人称单数，使用 goes。"),
    ("谓语动词", "They ___ football after class yesterday.", ["play", "plays", "played", "playing"], "played", "yesterday 表示过去，使用 played。"),
    ("一般过去时", "We ___ the museum last Sunday.", ["visit", "visited", "visits", "visiting"], "visited", "last Sunday 表示过去，使用 visited。"),
    ("非谓语动词", "I enjoy ___ English stories.", ["read", "reading", "reads", "to read"], "reading", "enjoy 后接动名词。"),
    ("阅读理解", "The passage says Tom takes a bus to school. How does Tom go to school?", ["By bus", "By bike", "On foot", "By car"], "By bus", "材料直接说明 Tom takes a bus。"),
]

QUESTION_VARIANTS = [
    [
        "My sister ___ to school every day.",
        "The boys ___ basketball after class yesterday.",
        "Our class ___ the museum last Sunday.",
        "I enjoy ___ short English stories.",
        "The passage says Tom travels by bus. How does he go to school?",
    ],
    [
        "Her friend ___ to school every day.",
        "The students ___ football yesterday afternoon.",
        "We ___ the museum last weekend.",
        "I enjoy ___ books in English.",
        "Tom takes a bus each morning. How does he travel?",
    ],
    [
        "The new student ___ to school every day.",
        "They ___ a match yesterday.",
        "My family ___ the museum last Sunday.",
        "She enjoys ___ English stories.",
        "Tom goes to school on a bus. How does Tom go there?",
    ],
    [
        "Our teacher says she ___ to school every day.",
        "They ___ football together yesterday.",
        "Our group ___ the museum last Sunday.",
        "The pupil enjoys ___ English stories.",
        "Tom rides the bus to school. Which transport does he use?",
    ],
]


def refresh_seed_question_stems(db: Session, classroom_id: int) -> None:
    assignments = db.scalars(select(Assignment).where(
        Assignment.class_id == classroom_id, Assignment.title.like("谓语动词与基础语法巩固 %")
    ).order_by(Assignment.assigned_at)).all()
    for assignment_index, assignment in enumerate(assignments[:4]):
        for question_index, relation in enumerate(assignment.questions[:5]):
            question = relation.question
            if question.source == "seed" and question.stem == QUESTION_TEMPLATES[question_index][1]:
                question.stem = QUESTION_VARIANTS[assignment_index][question_index]
    db.commit()


def seed_learning_data(db: Session) -> None:
    classroom = db.scalar(select(Class).where(Class.name == "高一（3）班"))
    if classroom is None:
        return
    points = {}
    for name, category in POINTS:
        point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.name == name))
        if point is None:
            point = KnowledgePoint(name=name, category=category)
            db.add(point)
            db.flush()
        points[name] = point

    db.commit()
    if db.scalar(select(Assignment.id).where(Assignment.class_id == classroom.id).limit(1)) is not None:
        refresh_seed_question_stems(db, classroom.id)
        return

    students = db.scalars(select(Student).where(Student.class_id == classroom.id).order_by(Student.id)).all()
    base_date = datetime(2026, 9, 10, 17, 0)
    for assignment_index in range(4):
        assigned_at = base_date + timedelta(days=7 * assignment_index)
        assignment = Assignment(
            class_id=classroom.id,
            title=f"谓语动词与基础语法巩固 {assignment_index + 1}",
            mode="class_unified",
            status="analyzed",
            assigned_at=assigned_at,
        )
        db.add(assignment)
        db.flush()
        questions = []
        for order, (point_name, stem, options, answer, explanation) in enumerate(QUESTION_TEMPLATES, start=1):
            question = Question(
                type="single_choice",
                stem=QUESTION_VARIANTS[assignment_index][order - 1],
                options=options,
                answer=answer,
                explanation=explanation,
                difficulty="基础",
                source="seed",
                knowledge_points=[points[point_name]],
            )
            db.add(question)
            db.flush()
            db.add(AssignmentQuestion(assignment_id=assignment.id, question_id=question.id, order_no=order, score=20))
            questions.append((question, points[point_name]))

        for student_index, student in enumerate(students):
            submission = StudentSubmission(
                assignment_id=assignment.id,
                student_id=student.id,
                submitted_at=assigned_at + timedelta(hours=2),
                total_score=0,
            )
            db.add(submission)
            db.flush()
            score = 0
            for question_index, (question, point) in enumerate(questions):
                # Demo patterns: Zhang/verb, Li/non-finite, Wang/tense, Zhao/reading.
                if student_index == 0:
                    correct = question_index not in (0, 1) or (assignment_index == 0 and question_index == 1)
                elif student_index == 1:
                    correct = question_index != 3 or assignment_index == 0
                elif student_index == 2:
                    correct = question_index != 2 or assignment_index == 0
                elif student_index == 3:
                    correct = question_index != 4 or assignment_index == 0
                else:
                    correct = (assignment_index + student_index + question_index) % 7 != 0
                answer_text = question.answer if correct else next(option for option in question.options if option != question.answer)
                answer = StudentAnswer(
                    submission_id=submission.id,
                    question_id=question.id,
                    answer_text=answer_text,
                    is_correct=correct,
                    score=20 if correct else 0,
                )
                db.add(answer)
                db.flush()
                db.add(LearningRecord(
                    student_id=student.id,
                    assignment_id=assignment.id,
                    question_id=question.id,
                    student_answer_id=answer.id,
                    knowledge_point_id=point.id,
                    is_correct=correct,
                    occurred_at=submission.submitted_at,
                ))
                score += answer.score
            submission.total_score = score
    db.commit()
    rebuild_profiles(db)
