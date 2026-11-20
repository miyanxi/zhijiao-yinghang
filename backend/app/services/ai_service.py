import json
import os
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from ..schemas.teaching import (DraftQuestionData, GeneratedQuestions, GoalDraftData,
                                LessonPlanGenerated, LessonSection, QualityReviewResult)
from ..schemas.manager import ManagerIntentData, ManagerSummaryData
from .name_matching import matched_names


class AIServiceError(Exception):
    pass


@dataclass
class AIResult:
    data: BaseModel
    source: str


LESSON_SECTIONS = [
    ("objectives", "教学目标"),
    ("learning_analysis", "学情分析"),
    ("key_points", "教学重点"),
    ("difficult_points", "教学难点"),
    ("teaching_flow", "教学流程"),
    ("explanation", "知识讲解"),
    ("examples", "示例"),
    ("class_practice", "课堂练习"),
    ("consolidation", "巩固练习"),
    ("homework", "作业"),
    ("evaluation", "教学评价"),
    ("reflection", "教学反思"),
]


class AIService:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.test_demo_generation = os.getenv("ENABLE_TEST_DEMO_GENERATION") == "1"
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
        self.endpoint = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")

    @property
    def source(self) -> str:
        return "deepseek" if self.api_key else "demo"

    def require_model(self) -> None:
        if not self.api_key and not self.test_demo_generation:
            raise AIServiceError("未配置 DEEPSEEK_API_KEY，无法调用 AI。请配置密钥并重启后端服务。")

    def _complete(self, task: str, context: dict, schema: type[BaseModel]) -> BaseModel:
        if not self.api_key:
            raise AIServiceError("未配置 DEEPSEEK_API_KEY，无法调用 AI。请配置密钥并重启后端服务。")
        body = json.dumps({
            "model": self.model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "你是高中英语教师的教学内容助理。只返回符合任务要求的 JSON 对象。教师负责最终审核，不执行发布或教学决策。"},
                {"role": "user", "content": json.dumps({"task": task, "context": context, "output_schema": schema.model_json_schema()}, ensure_ascii=False)},
            ],
        }, ensure_ascii=False).encode("utf-8")
        request = Request(self.endpoint, data=body, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            content = payload["choices"][0]["message"]["content"]
            return schema.model_validate(json.loads(content))
        except HTTPError as exc:
            raise AIServiceError(f"DeepSeek 请求失败（HTTP {exc.code}），请检查密钥、余额和网络后重试") from exc
        except (URLError, TimeoutError) as exc:
            raise AIServiceError("无法连接 DeepSeek，请检查网络或 DEEPSEEK_BASE_URL") from exc
        except (KeyError, json.JSONDecodeError, ValidationError) as exc:
            raise AIServiceError("DeepSeek 返回内容不符合结构要求，请稍后重试") from exc

    def understand_manager_request(self, message: str, student_names: list[str], point_names: list[str]) -> AIResult:
        if self.api_key:
            data = self._complete(
                "识别高中英语教师工作台意图。只能返回给定枚举中的意图；发布、删除、绕过审核或无法匹配的要求必须标为 unsupported。不得执行任何操作。",
                {"message": message, "allowed_students": student_names,
                 "allowed_knowledge_points": point_names,
                 "intents": ["class_analysis", "student_analysis", "lesson_prep",
                             "class_assignment", "targeted_training", "unsupported"]},
                ManagerIntentData,
            )
        else:
            student_matches = matched_names(message, student_names)
            point_matches = matched_names(message, point_names)
            if any(word in message.lower() for word in ("删除", "发布", "绕过", "sql", "自动确认", "自动决定")):
                intent = "unsupported"
            elif any(word in message for word in ("专项训练", "训练", "专项练习")):
                intent = "targeted_training"
            elif "教案" in message:
                intent = "lesson_prep"
            elif any(word in message for word in ("统一作业", "班级作业", "出作业")):
                intent = "class_assignment"
            elif student_matches and any(word in message for word in ("学情", "问题", "画像", "表现", "成绩", "分析", "看看")):
                intent = "student_analysis"
            elif any(word in message for word in ("班级学情", "全班", "班级表现", "班级分析")):
                intent = "class_analysis"
            else:
                intent = "unsupported"
            minutes = re.search(r"(\d+)\s*分钟", message)
            count = re.search(r"(\d+)\s*题", message)
            data = ManagerIntentData(
                intent=intent,
                student_name=student_matches[0] if len(student_matches) == 1 else None,
                knowledge_point_name=point_matches[0] if len(point_matches) == 1 else None,
                duration_minutes=int(minutes.group(1)) if minutes else None,
                question_count=int(count.group(1)) if count else None,
            )
        return AIResult(data, self.source)

    def summarize_manager_evidence(self, title: str, metrics: list[dict], evidence: list[str], fallback: str) -> AIResult:
        if self.api_key:
            data = self._complete(
                "根据给定指标和依据写一句简洁的高中英语教学观察；不得补充未给出的数字、诊断或决策建议。",
                {"title": title, "metrics": metrics, "evidence": evidence},
                ManagerSummaryData,
            )
        else:
            data = ManagerSummaryData(summary=fallback)
        return AIResult(data, self.source)

    def parse_goal(self, raw_input: str, grade: str, points: list[dict], class_memory: dict | None = None) -> AIResult:
        self.require_model()
        if self.api_key:
            data = self._complete("解析教学目标，保留教师原意和具体课程主题。只使用提供的知识点 ID；若目录中没有对应知识点，返回空的 knowledge_point_ids，不要强行映射到其他知识点。班级情况必须只依据给定历史学情，教学建议只围绕本节课和相关问题，不要罗列无关数字。", {
                "raw_input": raw_input, "grade": grade, "knowledge_points": points,
                "class_memory": class_memory or {},
            }, GoalDraftData)
        else:
            matches = [point for point in points if point["name"] in raw_input]
            names = [point["name"] for point in matches]
            topic = "、".join(names) if names else re.sub(
                r"^(今天|这节课|本节课|我|我要|想要|准备|计划|要|讲|学习|复习|关于|的)+",
                "", raw_input.strip(),
            )
            if not names:
                topic = re.sub(r"(的知识点|知识点|的内容|内容|怎么讲|如何讲)[。！？!?.]*$", "", topic).strip(" ，。！？!?.") or raw_input.strip()
                topic = topic[:200]
            data = GoalDraftData(
                topic=topic,
                knowledge_point_ids=[point["id"] for point in matches],
                objectives=[f"理解并运用{topic}的基础用法", f"通过练习辨析{topic}的常见错误"],
                key_points=f"{topic}的核心规则与实际运用",
                difficult_points=f"{topic}在具体语境中的辨析",
                class_context=(class_memory or {}).get("summary") or "当前暂无与本节课直接相关的历史学情记录。",
                teaching_advice=(class_memory or {}).get("advice") or f"建议围绕{topic}安排示例、练习和课堂反馈。",
                teacher_requirements=None,
            )
        return AIResult(data, self.source)

    def generate_lesson(self, context: dict) -> AIResult:
        self.require_model()
        if self.api_key:
            data = self._complete("生成教学教案草稿，sections.key 使用给定固定键，时间总和尽量匹配课堂时间。学情分析只写与本节课知识点相关的总体判断和课堂建议，不要堆砌精确数字。教学评价和教学反思不在备课阶段生成，它们由教师课后填写。", {
                **context, "section_keys": LESSON_SECTIONS,
            }, LessonPlanGenerated)
        else:
            topic = context["goal"]["topic"]
            minutes = context["duration_minutes"]
            durations = [0, 0, 0, 0, 5, 10, 5, 10, 8, 5, 0, 0]
            scale = minutes / sum(durations)
            durations = [round(value * scale) for value in durations]
            durations[4] += minutes - sum(durations)
            contents = [
                "能识别并正确使用" + topic + "，在语境中解释选择依据。",
                context.get("learning_analysis") or "围绕本节课知识点，先处理班级共同的易错点，再安排由易到难的练习。",
                context["goal"]["key_points"],
                context["goal"]["difficult_points"],
                "导入情境 → 规则归纳 → 示例辨析 → 同伴练习 → 课堂反馈。",
                "用对比例句呈现" + topic + "的结构和使用条件。",
                "展示两个正确表达与一个常见错误，由学生说明原因。",
                "安排短句辨析和改写，教师观察学生的理由表达。",
                "根据当堂错误调整巩固题数量与讲解节奏。",
                "布置一套与本节课目标一致的全班统一巩固作业，待教师审核后使用。",
                "",
                "",
            ]
            data = LessonPlanGenerated(
                title=f"{topic}教学设计（演示草稿）",
                sections=[LessonSection(key=key, title=title, content=contents[index], duration_minutes=durations[index])
                          for index, (key, title) in enumerate(LESSON_SECTIONS)],
            )
        return AIResult(data, self.source)

    def regenerate_section(self, context: dict, key: str) -> AIResult:
        self.require_model()
        if self.api_key:
            data = self._complete("只重新生成指定教案模块，不返回其他模块。新内容必须与 previous_content 明显不同，但继续围绕同一教学目标和本节课相关学情。", {**context, "section_key": key}, LessonSection)
        else:
            title = dict(LESSON_SECTIONS)[key]
            first = f"围绕{context['topic']}重新组织{title}：{context.get('teaching_advice') or '先观察学生表达，再通过针对性示例巩固。'}"
            second = f"{title}调整为先展示真实语境，再请学生解释{context['topic']}的判断依据，最后由教师归纳共性错误。"
            data = LessonSection(
                key=key,
                title=title,
                content=second if context.get("previous_content") == first else first,
                duration_minutes=context["duration_minutes"],
            )
        return AIResult(data, self.source)

    def generate_questions(self, context: dict) -> AIResult:
        self.require_model()
        if self.api_key:
            data = self._complete("生成与本节课高度相关的班级统一英语作业草稿。必须围绕 goal.topic、goal.objectives、goal.key_points 和给定知识点生成，不得套用其他课程的固定题库。必须生成多样题型：题量不少于3时至少包含 fill_blank、single_choice、multiple_choice 各一道。单选答案必须等于 options 中一个选项的完整原文；多选答案必须是 options 中至少两个不同选项的完整原文，以 || 连接，例如 选项原文一||选项原文二，不能写 A/B/C、序号或解释；填空题 options 必须为空。知识点 ID 只能取提供值，题量严格匹配。若 context 包含 validation_feedback，必须针对反馈修正后重新生成整套题。题干可以是中文或英文，允许中文标点。", context, GeneratedQuestions)
        else:
            templates = {
                "谓语动词": [
                    ("She ___ to school every morning.", ["go", "goes", "went", "going"], "goes", "第三人称单数一般现在时使用 goes。"),
                    ("They ___ football yesterday.", ["play", "plays", "played", "playing"], "played", "yesterday 提示一般过去时。"),
                    ("My brother ___ English very well.", ["speak", "speaks", "spoke", "speaking"], "speaks", "第三人称单数使用 speaks。"),
                    ("The students ___ ready for the lesson now.", ["is", "are", "was", "be"], "are", "复数主语与 are 搭配。"),
                    ("He ___ his homework before dinner yesterday.", ["finish", "finishes", "finished", "finishing"], "finished", "过去时间提示使用 finished。"),
                ],
                "一般过去时": [
                    ("We ___ the museum last Sunday.", ["visit", "visited", "visits", "visiting"], "visited", "last Sunday 提示一般过去时。"),
                    ("I ___ a letter to my friend yesterday.", ["write", "wrote", "writes", "writing"], "wrote", "write 的过去式是 wrote。"),
                    ("She ___ at home last night.", ["is", "are", "was", "were"], "was", "单数主语过去时使用 was。"),
                ],
                "非谓语动词": [
                    ("I enjoy ___ English stories.", ["read", "reading", "reads", "to read"], "reading", "enjoy 后接动名词。"),
                    ("She decided ___ early.", ["leave", "leaving", "to leave", "left"], "to leave", "decide 后接不定式。"),
                    ("The boy stopped ___ when the teacher entered.", ["talk", "talking", "talked", "to talk"], "talking", "stop doing 表示停止正在做的事。"),
                ],
                "阅读理解": [
                    ("Tom goes to school by bus. How does Tom go to school?", ["By bus", "By bike", "On foot", "By car"], "By bus", "材料直接说明 by bus。"),
                    ("Amy reads in the library after school. Where does Amy read?", ["At home", "In the library", "At school", "In the park"], "In the library", "材料直接说明 in the library。"),
                    ("Jack visits his grandparents on Sunday. When does Jack visit them?", ["On Monday", "On Friday", "On Sunday", "On Saturday"], "On Sunday", "材料直接说明 on Sunday。"),
                ],
            }
            available = [(point["knowledge_point_id"], point["name"]) for point in context["knowledge_points"] if point["name"] in templates]
            if not available:
                raise AIServiceError("当前知识点没有演示题库，请配置 DeepSeek 后生成")
            multi_examples = {
                "谓语动词": (
                    "下列句子中，哪些谓语动词形式正确？",
                    ["She goes to school every day.", "They play football after class.",
                     "He go to school every day.", "They plays football after class."],
                    "主谓一致要求第三人称单数用 goes，复数主语用 play。",
                ),
                "一般过去时": (
                    "下列句子中，哪些正确使用了一般过去时？",
                    ["We visited the museum yesterday.", "She wrote a letter last night.",
                     "We visit the museum yesterday.", "She writes a letter last night."],
                    "yesterday 与 last night 表示过去时间，应使用过去式。",
                ),
                "非谓语动词": (
                    "下列句子中，哪些非谓语动词使用正确？",
                    ["I enjoy reading stories.", "She decided to leave early.",
                     "I enjoy read stories.", "She decided leaving early."],
                    "enjoy 后接动名词，decide 后接不定式。",
                ),
                "阅读理解": (
                    "短文说 Tom 乘公交上学。哪些表述与短文一致？",
                    ["Tom goes to school by bus.", "Tom takes a bus to school.",
                     "Tom walks to school.", "Tom rides a bike to school."],
                    "前两句都表达乘公交上学。",
                ),
            }
            questions = []
            for index in range(context["question_count"]):
                point_id, point_name = available[index % len(available)]
                variants = templates[point_name]
                variant_index = index // len(available)
                stem, options, answer, explanation = variants[variant_index % len(variants)]
                if variant_index >= len(variants):
                    stem = f"练习组 {variant_index // len(variants) + 1}：{stem}"
                type_cycle = context.get("question_types") or ("single_choice", "multiple_choice", "fill_blank")
                question_type = type_cycle[index % len(type_cycle)]
                if question_type == "multiple_choice":
                    stem, options, explanation = multi_examples[point_name]
                    answer = "||".join(options[:2])
                elif question_type == "fill_blank":
                    stem = f"请在横线处填入合适形式：{stem}"
                    options = []
                questions.append(DraftQuestionData(
                    type=question_type, stem=stem, options=options, answer=answer,
                    explanation=explanation, knowledge_point_id=point_id,
                    difficulty=context["difficulty"],
                ))
            data = GeneratedQuestions(title=f"{context['topic']}班级统一作业（演示草稿）", questions=questions)
        return AIResult(data, self.source)

    def generate_targeted_training(self, context: dict) -> AIResult:
        if self.api_key:
            data = self._complete(
                "针对指定学生的持续性知识点问题生成单选专项训练。只使用给定知识点 ID，结合近期错误；题量严格匹配，答案必须是选项原文。",
                context, GeneratedQuestions,
            )
            return AIResult(data, self.source)
        result = self.generate_questions(context | {"question_types": ["single_choice"]})
        result.data.title = f"{context['student_name']} · {context['topic']}专项训练（演示草稿）"
        return result

    def review_question(self, question: DraftQuestionData, point_name: str) -> AIResult:
        self.require_model()
        issues = []
        if question.type in ("single_choice", "multiple_choice"):
            if len(question.options) != 4 or len(set(question.options)) != 4:
                issues.append("选择题须为四个互不重复的选项")
            answer_values = question.answer_values
            if question.type == "single_choice" and question.answer not in question.options:
                issues.append("标准答案不在选项中")
            if question.type == "multiple_choice" and (len(answer_values) < 2 or any(item not in question.options for item in answer_values)):
                issues.append("多选题答案必须包含至少两个有效选项")
        elif question.options:
            issues.append("填空题不应包含选择题选项")
        if not question.answer.strip():
            issues.append("缺少标准答案")
        if not question.stem.strip() or len(question.stem.strip()) < 5:
            issues.append("题干描述不完整")
        if not question.explanation.strip():
            issues.append("缺少答案解析")
        if self.api_key and not issues:
            result = self._complete("检查高中英语题目的语法、拼写、答案唯一性、知识点匹配、难度、材料与问题一致性，只返回 issues 数组。中文题干和中文标点均有效；不要仅因题干为中文或没有英文问号就报告问题。", {
                "question": question.model_dump(), "knowledge_point": point_name,
            }, QualityReviewResult)
            issues.extend(result.issues)
        return AIResult(QualityReviewResult(issues=issues), self.source)


def get_ai_service() -> AIService:
    return AIService()
