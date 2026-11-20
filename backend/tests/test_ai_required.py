import asyncio
import os
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.teaching import (DraftQuestionData, GeneratedQuestions, GoalDraftData,
                                  LessonPlanGenerated, LessonSection, QualityReviewResult)
from app.services.ai_service import AIService, LESSON_SECTIONS
from app.services.ai_service import AIResult
from support import IsolatedDatabaseTest


class AIRequiredTest(IsolatedDatabaseTest):
    def test_invalid_multiple_choice_is_retried_without_fallback(self):
        asyncio.run(self._check_retry())

    async def _check_retry(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            goal = await client.post("/api/v1/teaching-goals", json={
                "class_id": 1, "raw_input": "阅读理解做题方法", "topic": "阅读理解做题方法",
                "knowledge_point_ids": [4], "objectives": ["理解主旨与细节"],
                "key_points": "阅读理解", "difficult_points": "细节定位",
                "class_context": "已有阅读练习", "teaching_advice": "结合短文练习", "source": "teacher",
            })
            self.assertEqual(goal.status_code, 201, goal.text)
            goal_id = goal.json()["id"]
            await client.post(f"/api/v1/teaching-goals/{goal_id}/confirm")
            contexts = []

            def generated(context):
                contexts.append(context)
                point_id = context["knowledge_point_ids"][0]
                options = ["主旨", "细节", "推断", "词义"]
                questions = [
                    DraftQuestionData(type="fill_blank", stem="根据短文填写答案", options=[], answer="主旨", explanation="阅读定位", knowledge_point_id=point_id, difficulty="中等"),
                    DraftQuestionData(type="single_choice", stem="选择文章主旨答案", options=options, answer="主旨", explanation="概括全文", knowledge_point_id=point_id, difficulty="中等"),
                    DraftQuestionData(type="multiple_choice", stem="选择两项阅读策略", options=options,
                                      answer="A||Z" if "validation_feedback" not in context else "A||B",
                                      explanation="关注主旨和细节", knowledge_point_id=point_id, difficulty="中等"),
                ]
                return AIResult(GeneratedQuestions(title="阅读理解练习", questions=questions), "deepseek")

            with patch("app.api.assignment_drafts.get_ai_service") as service:
                service.return_value.generate_questions.side_effect = generated
                service.return_value.review_question.return_value = AIResult(QualityReviewResult(issues=[]), "deepseek")
                response = await client.post("/api/v1/assignment-drafts/generate", json={"teaching_goal_id": goal_id, "question_count": 3})
                self.assertEqual(response.status_code, 201, response.text)
                self.assertEqual(response.json()["source"], "deepseek")
                self.assertEqual(response.json()["questions"][2]["answer"], "主旨||细节")
                self.assertEqual(len(contexts), 2)
                self.assertIn("多选题答案", contexts[1]["validation_feedback"])

            with patch("app.api.assignment_drafts.get_ai_service") as service:
                service.return_value.generate_questions.side_effect = lambda context: generated(context | {"validation_feedback": "use labels"})
                service.return_value.review_question.return_value = AIResult(QualityReviewResult(issues=[]), "deepseek")
                labeled = await client.post("/api/v1/assignment-drafts/generate", json={"teaching_goal_id": goal_id, "question_count": 3})
                self.assertEqual(labeled.status_code, 201, labeled.text)
                self.assertEqual(labeled.json()["questions"][2]["answer"], "主旨||细节")

            with patch("app.api.assignment_drafts.get_ai_service") as service:
                service.return_value.generate_questions.side_effect = lambda context: generated({key: value for key, value in context.items() if key != "validation_feedback"})
                rejected = await client.post("/api/v1/assignment-drafts/generate", json={"teaching_goal_id": goal_id, "question_count": 3})
                self.assertEqual(rejected.status_code, 502)
                drafts = (await client.get("/api/v1/assignment-drafts?class_id=1")).json()
                self.assertEqual(len(drafts), 2)

    def test_generation_never_falls_back_in_normal_mode(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "0"}):
            asyncio.run(self._check_missing_key())

    def test_three_workbenches_use_model_output(self):
        calls = []

        def fake_complete(_service, task, context, schema):
            calls.append(schema.__name__)
            if schema is GoalDraftData:
                return GoalDraftData(
                    topic="AI生成的一般现在时", knowledge_point_ids=[],
                    objectives=["AI生成的目标"], key_points="AI重点", difficult_points="AI难点",
                    class_context="AI依据历史记录总结的学情", teaching_advice="AI课堂建议",
                )
            if schema is LessonPlanGenerated:
                return LessonPlanGenerated(title="AI生成的教案", sections=[
                    LessonSection(key=key, title=title, content=f"AI生成的{title}", duration_minutes=0)
                    for key, title in LESSON_SECTIONS
                ])
            if schema is GeneratedQuestions:
                point_id = context["knowledge_point_ids"][0]
                types = ["fill_blank", "single_choice", "multiple_choice"]
                return GeneratedQuestions(title="AI生成的统一作业", questions=[
                    DraftQuestionData(type=types[i % 3], stem=f"AI生成的题目{i}：请完成本课练习", options=[] if types[i % 3] == "fill_blank" else ["goes", "go", "went", "going"],
                                      answer="goes" if types[i % 3] != "multiple_choice" else "goes||go", explanation="AI解析", knowledge_point_id=point_id,
                                      difficulty="中等")
                    for i in range(context["question_count"])
                ])
            if schema is QualityReviewResult:
                return QualityReviewResult(issues=[])
            raise AssertionError(f"unexpected schema: {schema}")

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only-key", "ENABLE_TEST_DEMO_GENERATION": "0"}), \
                patch.object(AIService, "_complete", fake_complete):
            asyncio.run(self._check_model_output())
        self.assertIn("GoalDraftData", calls)
        self.assertIn("LessonPlanGenerated", calls)
        self.assertIn("GeneratedQuestions", calls)
        self.assertEqual(calls.count("QualityReviewResult"), 3)

    async def _check_model_output(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            parsed = await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "今天讲一般现在时并安排课堂练习",
            })
            self.assertEqual(parsed.status_code, 200, parsed.text)
            self.assertEqual(parsed.json()["source"], "deepseek")
            self.assertEqual(parsed.json()["class_context"], "AI依据历史记录总结的学情")
            self.assertEqual(parsed.json()["objectives"], ["AI生成的目标"])
            goal = await client.post("/api/v1/teaching-goals", json=parsed.json() | {
                "class_id": 1, "raw_input": "今天讲一般现在时并安排课堂练习",
            })
            self.assertEqual(goal.status_code, 201, goal.text)
            goal_id = goal.json()["id"]
            self.assertEqual((await client.post(f"/api/v1/teaching-goals/{goal_id}/confirm")).status_code, 200)
            plan = await client.post("/api/v1/lesson-plans/generate", json={"teaching_goal_id": goal_id})
            self.assertEqual(plan.status_code, 201, plan.text)
            self.assertEqual(plan.json()["title"], "AI生成的教案")
            self.assertEqual(plan.json()["source"], "deepseek")
            assignment = await client.post("/api/v1/assignment-drafts/generate", json={
                "teaching_goal_id": goal_id, "question_count": 3,
            })
            self.assertEqual(assignment.status_code, 201, assignment.text)
            self.assertEqual(assignment.json()["title"], "AI生成的统一作业")
            self.assertEqual(assignment.json()["source"], "deepseek")

    async def _check_missing_key(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            parsed = await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "今天讲一般现在时并安排课堂练习",
            })
            self.assertEqual(parsed.status_code, 503)
            self.assertIn("DEEPSEEK_API_KEY", parsed.json()["detail"])

            goal = await client.post("/api/v1/teaching-goals", json={
                "class_id": 1, "raw_input": "一般现在时", "topic": "一般现在时",
                "knowledge_point_ids": [], "objectives": ["理解一般现在时"],
                "key_points": "一般现在时的基本用法", "difficult_points": "语境辨析",
                "class_context": "暂无本课相关记录", "teaching_advice": "结合语境练习",
                "source": "teacher",
            })
            self.assertEqual(goal.status_code, 201, goal.text)
            goal_id = goal.json()["id"]
            self.assertEqual((await client.post(f"/api/v1/teaching-goals/{goal_id}/confirm")).status_code, 200)

            plan = await client.post("/api/v1/lesson-plans/generate", json={"teaching_goal_id": goal_id})
            assignment = await client.post("/api/v1/assignment-drafts/generate", json={
                "teaching_goal_id": goal_id, "question_count": 3,
            })
            self.assertEqual(plan.status_code, 503)
            self.assertEqual(assignment.status_code, 503)
            self.assertEqual((await client.get("/api/v1/lesson-plans?class_id=1")).json(), [])
            self.assertEqual((await client.get("/api/v1/assignment-drafts?class_id=1")).json(), [])


if __name__ == "__main__":
    import unittest
    unittest.main()
