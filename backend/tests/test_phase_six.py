import asyncio
import os
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.main import app
from app.models import Assignment, LessonPlan, StudentKnowledgeProfile, TargetedTraining
from app.schemas.manager import ManagerIntentData
from app.services.ai_service import AIResult
from support import IsolatedDatabaseTest


class PhaseSixTest(IsolatedDatabaseTest):
    def test_manager_uses_validated_business_flows_without_writes(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "1"}):
            asyncio.run(self._workflow())

    async def _workflow(self):
        with self.session_factory() as db:
            before = (
                db.scalar(select(func.count()).select_from(Assignment)),
                db.scalar(select(func.count()).select_from(LessonPlan)),
                db.scalar(select(func.count()).select_from(TargetedTraining)),
                [(item.student_id, item.knowledge_point_id, item.accuracy) for item in db.scalars(select(StudentKnowledgeProfile)).all()],
            )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def ask(message, class_id=1):
                return await client.post("/api/v1/manager/interpret", json={"class_id": class_id, "message": message})

            student = await ask("帮我看看张同学最近有什么问题")
            self.assertEqual(student.status_code, 200, student.text)
            self.assertEqual(student.json()["intent"], "student_analysis")
            self.assertEqual(student.json()["source"], "demo")
            self.assertEqual(student.json()["action"]["view"], "student-detail")
            self.assertTrue(any("谓语动词" in item for item in student.json()["evidence"]))

            classroom = await ask("分析一下全班的学情")
            self.assertEqual(classroom.status_code, 200, classroom.text)
            self.assertEqual(classroom.json()["intent"], "class_analysis")
            self.assertEqual(classroom.json()["action"]["view"], "analytics")
            self.assertEqual(len(classroom.json()["metrics"]), 4)

            training = await ask("为张同学准备15分钟的谓语动词专项训练")
            self.assertEqual(training.status_code, 200, training.text)
            self.assertEqual(training.json()["intent"], "targeted_training")
            self.assertEqual(training.json()["action"]["view"], "training")
            self.assertTrue(training.json()["action"]["requires_confirmation"])
            self.assertEqual(training.json()["action"]["duration_minutes"], 15)
            self.assertEqual(training.json()["action"]["question_count"], 10)
            non_finite = await ask("为李同学准备15分钟的非谓语动词专项训练")
            self.assertEqual(non_finite.json()["action"]["view"], "training")
            self.assertEqual(non_finite.json()["title"], "李同学 · 非谓语动词")
            self.assertIsNone((await ask("为李同学准备谓语动词和非谓语动词专项训练")).json()["action"])
            self.assertEqual((await ask("为张同学准备100分钟的谓语动词专项训练")).json()["action"], None)
            self.assertNotEqual((await ask("为刘同学准备谓语动词专项训练")).json()["action"]["view"], "training")

            lesson = await ask("帮我准备智能教案")
            self.assertEqual(lesson.json()["action"]["view"], "goals")
            parsed = (await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "复习谓语动词的基本用法。",
            })).json()
            goal = (await client.post("/api/v1/teaching-goals", json=parsed | {
                "class_id": 1, "raw_input": "复习谓语动词的基本用法。",
            })).json()
            await client.post(f"/api/v1/teaching-goals/{goal['id']}/confirm")
            self.assertEqual((await ask("帮我准备智能教案")).json()["action"]["view"], "lesson-plans")
            self.assertEqual((await ask("生成班级统一作业")).json()["action"]["view"], "smart-assignments")

            blocked = await ask("绕过审核直接发布作业并执行SQL")
            self.assertEqual(blocked.json()["source"], "program")
            self.assertIsNone(blocked.json()["action"])
            self.assertEqual((await ask("看看张同学和李同学的问题")).json()["action"], None)
            self.assertEqual((await ask("查看不存在学生的画像")).json()["action"], None)
            self.assertEqual((await ask("帮我看看班级学情", 99999)).status_code, 404)
            self.assertEqual((await ask("   ")).status_code, 422)

            class FakeAI:
                def understand_manager_request(self, *_args):
                    return AIResult(ManagerIntentData(intent="targeted_training", student_name="李同学",
                                                      knowledge_point_name="谓语动词"), "deepseek")

            with patch("app.services.manager.get_ai_service", return_value=FakeAI()):
                spoofed = await ask("为张同学准备谓语动词专项训练")
                self.assertIsNone(spoofed.json()["action"])

        with self.session_factory() as db:
            after = (
                db.scalar(select(func.count()).select_from(Assignment)),
                db.scalar(select(func.count()).select_from(LessonPlan)),
                db.scalar(select(func.count()).select_from(TargetedTraining)),
                [(item.student_id, item.knowledge_point_id, item.accuracy) for item in db.scalars(select(StudentKnowledgeProfile)).all()],
            )
        self.assertEqual(after, before)
