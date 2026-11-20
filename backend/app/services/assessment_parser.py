import re

from pydantic import BaseModel, Field

from .ai_service import AIServiceError, get_ai_service


class ImportedQuestion(BaseModel):
    number: int = Field(ge=1)
    type: str = Field(pattern="^(single_choice|multiple_choice|fill_blank)$")
    stem: str = Field(min_length=5)
    options: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1)
    explanation: str = "由教师上传的参考答案导入。"
    knowledge_point_name: str = Field(min_length=1)


class ImportedPaper(BaseModel):
    title: str = Field(min_length=1)
    questions: list[ImportedQuestion] = Field(min_length=1)


class ExtractedStudentAnswers(BaseModel):
    answers: list[dict] = Field(min_length=1)


def parse_paper(paper_text: str, answer_key_text: str, point_names: list[str]) -> ImportedPaper:
    if not paper_text or not answer_key_text:
        raise AIServiceError("试卷和参考答案必须包含可提取的文字；扫描版 PDF 需要先 OCR")
    ai = get_ai_service()
    if ai.api_key:
        return ai._complete(
            "从教师上传的试卷和参考答案提取题目。只允许单选、多选、填空；严格逐题对应，不得补造题目、答案或知识点。多选答案用 || 连接选项原文。不能确认的题目不要输出。",
            {"paper_text": paper_text[:50000], "answer_key_text": answer_key_text[:30000], "knowledge_points": point_names},
            ImportedPaper,
        )
    # Demonstration parser accepts clearly numbered questions and explicit answers only.
    paper_lines = re.findall(r"(?m)^\s*(\d+)[.、．)]\s*(.{5,})$", paper_text)
    answer_lines = dict((int(n), value.strip()) for n, value in re.findall(r"(?m)^\s*(\d+)[.、．):：]\s*(.+)$", answer_key_text))
    questions = []
    for number_text, stem in paper_lines:
        number = int(number_text)
        if number not in answer_lines:
            continue
        point = next((name for name in point_names if name in stem), point_names[0] if point_names else "")
        if not point:
            continue
        questions.append(ImportedQuestion(number=number, type="fill_blank", stem=stem.strip(),
                                          answer=answer_lines[number], knowledge_point_name=point))
    if not questions:
        raise AIServiceError("演示解析无法识别题目与参考答案的对应关系，请配置 DeepSeek 或使用每行“1. 题目 / 1. 答案”的格式")
    return ImportedPaper(title="导入试卷", questions=questions)


def parse_student_answers(text: str, questions: list[dict]) -> dict[int, str]:
    if not text:
        raise AIServiceError("学生作业中没有可提取的文字；扫描版 PDF 或图片需要 OCR")
    ai = get_ai_service()
    if ai.api_key:
        parsed = ai._complete(
            "从学生作业文本提取逐题答案。只返回能明确对应题号的答案；不得推测、补答或评分。",
            {"student_work": text[:30000], "questions": questions}, ExtractedStudentAnswers,
        )
        return {int(item["number"]): str(item["answer"]).strip() for item in parsed.answers}
    return {int(number): value.strip() for number, value in re.findall(r"(?m)^\s*(\d+)[.、．):：]\s*(.+)$", text)}
