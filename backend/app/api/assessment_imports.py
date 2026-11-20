from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (AssessmentImport, Assignment, AssignmentQuestion, Class,
                      KnowledgePoint, Question, Student, StudentSubmission,
                      UploadedStudentWork)
from ..schemas.assignments import StudentSubmissionCreate, SubmittedAnswerCreate
from ..services.ai_service import AIServiceError
from ..services.assessment_parser import parse_paper, parse_student_answers
from ..services.file_extraction import FileExtractionError, extract_text
from .assignments import get_assignment, submit_answers

router = APIRouter(prefix="/assessment-imports", tags=["assessment-imports"])
MAX_FILE_BYTES = 8 * 1024 * 1024


class StudentAnswerCorrection(BaseModel):
    answers: dict[str, str]


class ImportedQuestionCorrection(BaseModel):
    stem: str = Field(min_length=5)
    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    knowledge_point_name: str = Field(min_length=1)


async def read_upload(file: UploadFile) -> str:
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="单个文件不能超过 8 MB")
    try:
        return extract_text(file.filename or "", content)
    except FileExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def read_import(item: AssessmentImport, db: Session) -> dict:
    detail = get_assignment(item.assignment_id, db)
    works = db.scalars(select(UploadedStudentWork).where(UploadedStudentWork.assessment_id == item.id).order_by(UploadedStudentWork.id.desc())).all()
    return {
        "id": item.id, "class_id": item.class_id, "assignment_id": item.assignment_id,
        "title": item.title, "status": item.status,
        "paper_file_name": item.paper_file_name, "answer_key_file_name": item.answer_key_file_name,
        "questions": [question.model_dump() for question in detail.questions],
        "works": [{"id": work.id, "student_id": work.student_id, "file_name": work.file_name,
                   "status": work.status, "extracted_answers": work.extracted_answers,
                   "score": work.score, "error_message": work.error_message} for work in works],
    }


@router.get("", response_model=list[dict])
def list_imports(class_id: int, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    return [read_import(item, db) for item in db.scalars(select(AssessmentImport).where(AssessmentImport.class_id == class_id).order_by(AssessmentImport.id.desc())).all()]


@router.post("", response_model=dict, status_code=201)
async def create_import(class_id: int = Form(...), title: str = Form(...),
                        paper: UploadFile = File(...), answer_key: UploadFile = File(...),
                        db: Session = Depends(get_db)) -> dict:
    if db.get(Class, class_id) is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    if not title.strip():
        raise HTTPException(status_code=422, detail="请填写试卷名称")
    paper_text = await read_upload(paper)
    answer_text = await read_upload(answer_key)
    points = db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)).all()
    try:
        parsed = parse_paper(paper_text, answer_text, [item.name for item in points])
    except AIServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    point_map = {point.name: point for point in points}
    assignment = Assignment(class_id=class_id, title=title.strip(), mode="class_unified", status="draft", assigned_at=datetime.utcnow())
    db.add(assignment)
    db.flush()
    total = len(parsed.questions)
    for index, item in enumerate(parsed.questions):
        point = point_map.get(item.knowledge_point_name)
        if point is None:
            db.rollback()
            raise HTTPException(status_code=422, detail=f"未知知识点：{item.knowledge_point_name}")
        if item.type in ("single_choice", "multiple_choice") and (len(item.options) != 4 or any(answer not in item.options for answer in item.answer.split("||"))):
            db.rollback()
            raise HTTPException(status_code=422, detail=f"第 {item.number} 题选项或答案不完整")
        question = Question(type=item.type, stem=item.stem, options=item.options,
                            answer=item.answer, explanation=item.explanation,
                            difficulty="中等", source="import", knowledge_points=[point])
        db.add(question)
        db.flush()
        score = round(100 / total, 2) if index < total - 1 else round(100 - round(100 / total, 2) * (total - 1), 2)
        db.add(AssignmentQuestion(assignment_id=assignment.id, question_id=question.id, order_no=item.number, score=score))
    imported = AssessmentImport(class_id=class_id, assignment_id=assignment.id, title=title.strip(),
                                paper_file_name=paper.filename or "paper", answer_key_file_name=answer_key.filename or "answer",
                                paper_text=paper_text, answer_key_text=answer_text, status="draft")
    db.add(imported)
    db.commit()
    return read_import(imported, db)


@router.post("/{import_id}/approve", response_model=dict)
def approve_import(import_id: int, db: Session = Depends(get_db)) -> dict:
    imported = db.get(AssessmentImport, import_id)
    if imported is None:
        raise HTTPException(status_code=404, detail="导入试卷不存在")
    if imported.status != "draft":
        raise HTTPException(status_code=409, detail="该试卷已经确认")
    imported.status = "approved"
    assignment = db.get(Assignment, imported.assignment_id)
    assignment.status = "published"
    db.commit()
    return read_import(imported, db)


@router.patch("/{import_id}/questions/{question_id}", response_model=dict)
def correct_imported_question(import_id: int, question_id: int,
                              payload: ImportedQuestionCorrection,
                              db: Session = Depends(get_db)) -> dict:
    imported = db.get(AssessmentImport, import_id)
    if imported is None:
        raise HTTPException(status_code=404, detail="导入试卷不存在")
    if imported.status != "draft":
        raise HTTPException(status_code=409, detail="已确认试卷不能修改")
    relation = db.scalar(select(AssignmentQuestion).where(
        AssignmentQuestion.assignment_id == imported.assignment_id,
        AssignmentQuestion.question_id == question_id,
    ))
    if relation is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.name == payload.knowledge_point_name.strip()))
    if point is None:
        raise HTTPException(status_code=422, detail="知识点不在课程目录中")
    question = relation.question
    question.stem = payload.stem.strip()
    question.answer = payload.answer.strip()
    question.explanation = payload.explanation.strip()
    question.knowledge_points = [point]
    db.commit()
    return read_import(imported, db)


@router.post("/{import_id}/student-work", response_model=dict, status_code=201)
async def upload_student_work(import_id: int, student_id: int = Form(...),
                              work: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    imported = db.get(AssessmentImport, import_id)
    if imported is None:
        raise HTTPException(status_code=404, detail="导入试卷不存在")
    if imported.status != "approved":
        raise HTTPException(status_code=409, detail="请先由教师确认试卷和参考答案")
    student = db.get(Student, student_id)
    if student is None or student.class_id != imported.class_id or student.status != "在读":
        raise HTTPException(status_code=422, detail="学生不属于当前班级或已停用")
    if db.scalar(select(StudentSubmission.id).where(StudentSubmission.assignment_id == imported.assignment_id,
                                                     StudentSubmission.student_id == student_id)):
        raise HTTPException(status_code=409, detail="该学生已经完成此试卷")
    text = await read_upload(work)
    detail = get_assignment(imported.assignment_id, db)
    try:
        extracted = parse_student_answers(text, [question.model_dump() for question in detail.questions])
    except AIServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    missing = [question.order_no for question in detail.questions if question.order_no not in extracted]
    if missing:
        raise HTTPException(status_code=422, detail=f"无法确认第 {', '.join(map(str, missing))} 题答案，请上传清晰文本或修正文件")
    record = UploadedStudentWork(assessment_id=import_id, student_id=student_id,
                                 file_name=work.filename or "work", extracted_text=text,
                                 extracted_answers={str(number): value for number, value in extracted.items()},
                                 status="pending_review")
    db.add(record)
    db.commit()
    return read_import(imported, db)


@router.post("/{import_id}/student-work/{work_id}/confirm", response_model=dict)
def confirm_student_work(import_id: int, work_id: int, db: Session = Depends(get_db)) -> dict:
    imported = db.get(AssessmentImport, import_id)
    work = db.get(UploadedStudentWork, work_id)
    if imported is None or work is None or work.assessment_id != import_id:
        raise HTTPException(status_code=404, detail="学生作业不存在")
    if work.status != "pending_review":
        raise HTTPException(status_code=409, detail="该作业已经确认")
    detail = get_assignment(imported.assignment_id, db)
    answers = [SubmittedAnswerCreate(question_id=question.question_id,
                                     answer_text=work.extracted_answers[str(question.order_no)])
               for question in detail.questions]
    submission = submit_answers(imported.assignment_id,
                                StudentSubmissionCreate(student_id=work.student_id, answers=answers), db)
    work.status = "graded"
    work.score = submission.total_score
    db.commit()
    return read_import(imported, db)


@router.patch("/{import_id}/student-work/{work_id}", response_model=dict)
def correct_student_work(import_id: int, work_id: int, payload: StudentAnswerCorrection,
                         db: Session = Depends(get_db)) -> dict:
    work = db.get(UploadedStudentWork, work_id)
    imported = db.get(AssessmentImport, import_id)
    if imported is None or work is None or work.assessment_id != import_id:
        raise HTTPException(status_code=404, detail="学生作业不存在")
    if work.status != "pending_review":
        raise HTTPException(status_code=409, detail="只有待确认的识别结果可以修改")
    detail = get_assignment(imported.assignment_id, db)
    expected = {str(question.order_no) for question in detail.questions}
    if set(payload.answers) != expected or any(not value.strip() for value in payload.answers.values()):
        raise HTTPException(status_code=422, detail="必须完整填写每道题的学生答案")
    work.extracted_answers = {key: value.strip() for key, value in payload.answers.items()}
    db.commit()
    return read_import(imported, db)
