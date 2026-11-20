import os
from io import BytesIO

from pypdf import PdfReader
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assignment, AssignmentPublication, AssignmentStudentWork, Student, StudentSubmission
from ..services.ai_service import AIServiceError
from ..services.assessment_parser import parse_student_answers
from ..services.file_extraction import FileExtractionError, extract_text
from ..services.demo_upload import DEMO_UPLOAD_MARKER
from .assignments import get_assignment, submit_answers
from ..schemas.assignments import StudentSubmissionCreate, SubmittedAnswerCreate

router = APIRouter(prefix="/assignments", tags=["assignment-uploads"])
MAX_FILE_BYTES = 8 * 1024 * 1024


def demo_upload_for(student: Student) -> bool:
    return (os.getenv("ZHJ_DEMO_UPLOAD") == "1"
            and student.name == "张同学" and student.student_no == "G1-001")


async def read_demo_pdf(file: UploadFile) -> None:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="演示模拟作答仅接受 PDF 文件")
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="单个文件不能超过 8 MB")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="上传文件不是有效的 PDF")
    try:
        if len(PdfReader(BytesIO(content)).pages) == 0:
            raise ValueError("PDF 没有页面")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="上传文件不是有效的 PDF") from exc


def demo_answers(questions: list) -> dict[int, str]:
    answers = {}
    for index, question in enumerate(questions):
        if index == 0:
            if question.type == "single_choice":
                answers[question.order_no] = next((option for option in question.options if option != question.answer), question.answer)
            elif question.type == "multiple_choice":
                correct = {item.strip() for item in question.answer.split("||")}
                pair = next((
                    (left, right)
                    for position, left in enumerate(question.options)
                    for right in question.options[position + 1:]
                    if {left, right} != correct
                ), None)
                answers[question.order_no] = "||".join(pair) if pair else question.answer
            else:
                answers[question.order_no] = "演示错误答案"
        else:
            answers[question.order_no] = question.answer
    return answers


async def read_work(file: UploadFile) -> str:
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="单个文件不能超过 8 MB")
    try:
        return extract_text(file.filename or "", content)
    except FileExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def result(assignment_id: int, db: Session) -> dict:
    assignment = db.get(Assignment, assignment_id)
    works = db.scalars(select(AssignmentStudentWork).where(AssignmentStudentWork.assignment_id == assignment_id).order_by(AssignmentStudentWork.id.desc())).all()
    return {"assignment_id": assignment_id, "title": assignment.title,
            "demo_upload_enabled": os.getenv("ZHJ_DEMO_UPLOAD") == "1", "works": [
        {"id": work.id, "student_id": work.student_id, "file_name": work.file_name,
         "status": work.status, "extracted_answers": work.extracted_answers,
         "score": work.score, "error_message": work.error_message,
         "demo_simulated": work.extracted_text == DEMO_UPLOAD_MARKER}
        for work in works
    ]}


@router.post("/{assignment_id}/student-works", response_model=dict, status_code=201)
async def upload_student_work(assignment_id: int, student_id: int = Form(...), work: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    assignment = db.get(Assignment, assignment_id)
    publication = db.scalar(select(AssignmentPublication).where(AssignmentPublication.assignment_id == assignment_id))
    student = db.get(Student, student_id)
    if assignment is None or publication is None or assignment.status not in ("published", "analyzed"):
        raise HTTPException(status_code=404, detail="只能上传已发布的班级统一作业")
    if student is None or student.class_id != assignment.class_id or student.status != "在读":
        raise HTTPException(status_code=422, detail="学生不属于当前班级或已停用")
    if db.scalar(select(StudentSubmission.id).where(StudentSubmission.assignment_id == assignment_id, StudentSubmission.student_id == student_id)):
        raise HTTPException(status_code=409, detail="该学生已经提交过此作业")
    if db.scalar(select(AssignmentStudentWork.id).where(
        AssignmentStudentWork.assignment_id == assignment_id,
        AssignmentStudentWork.student_id == student_id,
        AssignmentStudentWork.status == "pending_review",
    )):
        raise HTTPException(status_code=409, detail="该学生已有待教师确认的作业")
    detail = get_assignment(assignment_id, db)
    if demo_upload_for(student):
        await read_demo_pdf(work)
        text = DEMO_UPLOAD_MARKER
        extracted = demo_answers(detail.questions)
    else:
        text = await read_work(work)
        try:
            extracted = parse_student_answers(text, [question.model_dump() for question in detail.questions])
        except AIServiceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    missing = [question.order_no for question in detail.questions if question.order_no not in extracted]
    if missing:
        raise HTTPException(status_code=422, detail=f"无法确认第 {', '.join(map(str, missing))} 题答案，请上传清晰文本或修正文件")
    record = AssignmentStudentWork(assignment_id=assignment_id, student_id=student_id,
                                file_name=work.filename or "work", extracted_text=text,
                                extracted_answers={str(number): value for number, value in extracted.items()},
                                status="pending_review")
    db.add(record)
    db.commit()
    return result(assignment_id, db)


@router.get("/{assignment_id}/student-works", response_model=dict)
def list_student_works(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    if db.get(Assignment, assignment_id) is None:
        raise HTTPException(status_code=404, detail="作业不存在")
    return result(assignment_id, db)


@router.post("/{assignment_id}/student-works/{work_id}/confirm", response_model=dict)
def confirm_student_work(assignment_id: int, work_id: int, db: Session = Depends(get_db)) -> dict:
    work = db.get(AssignmentStudentWork, work_id)
    if work is None or work.assignment_id != assignment_id or work.status != "pending_review":
        raise HTTPException(status_code=404, detail="待确认的学生作业不存在")
    detail = get_assignment(assignment_id, db)
    answers = [SubmittedAnswerCreate(question_id=question.question_id,
                                     answer_text=work.extracted_answers[str(question.order_no)])
               for question in detail.questions]
    submission = submit_answers(assignment_id, StudentSubmissionCreate(student_id=work.student_id, answers=answers), db)
    work.status = "graded"
    work.score = submission.total_score
    db.commit()
    return result(assignment_id, db)
