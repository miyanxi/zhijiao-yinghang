import asyncio
import os
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from support import IsolatedDatabaseTest


class ProductRevisionTest(IsolatedDatabaseTest):
    def test_unlisted_lesson_topic_without_manual_point_selection(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "1"}):
            asyncio.run(self._unlisted_topic_workflow())

    async def _unlisted_topic_workflow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            catalog_before = (await client.get("/api/v1/teaching-goals/knowledge-points/catalog")).json()
            parsed = await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "今天我要讲一般现在时的知识点",
            })
            self.assertEqual(parsed.status_code, 200, parsed.text)
            self.assertEqual(parsed.json()["topic"], "一般现在时")
            self.assertEqual(parsed.json()["knowledge_point_ids"], [])
            self.assertEqual((await client.get("/api/v1/teaching-goals/knowledge-points/catalog")).json(), catalog_before)
            goal = await client.post("/api/v1/teaching-goals", json=parsed.json() | {
                "class_id": 1, "raw_input": "今天我要讲一般现在时的知识点",
            })
            self.assertEqual(goal.status_code, 201, goal.text)
            point_id = goal.json()["knowledge_point_ids"][0]
            catalog_after = (await client.get("/api/v1/teaching-goals/knowledge-points/catalog")).json()
            self.assertEqual(next(item["name"] for item in catalog_after if item["id"] == point_id), "一般现在时")

    def test_goal_memory_review_and_file_grading(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "1"}):
            asyncio.run(self._workflow())

    async def _workflow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            point = await client.post("/api/v1/teaching-goals/knowledge-points", json={
                "name": "作文时态", "category": "写作",
            })
            self.assertEqual(point.status_code, 201, point.text)
            self.assertEqual((await client.post("/api/v1/teaching-goals/knowledge-points", json={
                "name": "作文时态", "category": "写作",
            })).status_code, 409)
            parsed = await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "这节课讲作文时态和一般过去时，请结合班级情况。",
            })
            self.assertEqual(parsed.status_code, 200, parsed.text)
            self.assertIn("一般过去时", parsed.json()["class_context"])
            self.assertIn("作文", parsed.json()["class_context"])
            self.assertTrue(parsed.json()["teaching_advice"])
            goal = await client.post("/api/v1/teaching-goals", json=parsed.json() | {
                "class_id": 1, "raw_input": "这节课讲作文时态和一般过去时，请结合班级情况。",
            })
            self.assertEqual(goal.status_code, 201, goal.text)
            goal_id = goal.json()["id"]
            self.assertEqual((await client.delete(f"/api/v1/teaching-goals/{goal_id}")).status_code, 204)
            self.assertEqual((await client.get(f"/api/v1/teaching-goals/{goal_id}")).status_code, 404)

            parsed = (await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "复习谓语动词和一般过去时，完成课堂检测。",
            })).json()
            goal = (await client.post("/api/v1/teaching-goals", json=parsed | {
                "class_id": 1, "raw_input": "复习谓语动词和一般过去时，完成课堂检测。",
            })).json()
            goal_id = goal["id"]
            self.assertEqual((await client.post(f"/api/v1/teaching-goals/{goal_id}/confirm")).status_code, 200)
            plan = await client.post("/api/v1/lesson-plans/generate", json={"teaching_goal_id": goal_id})
            self.assertEqual(plan.status_code, 201, plan.text)
            plan_id = plan.json()["id"]
            plan_pdf = await client.get(f"/api/v1/lesson-plans/{plan_id}/pdf")
            self.assertEqual(plan_pdf.status_code, 200, plan_pdf.text if plan_pdf.status_code != 200 else "")
            self.assertTrue(plan_pdf.content.startswith(b"%PDF"))
            original = next(section["content"] for section in plan.json()["sections"] if section["key"] == "examples")
            regenerated = await client.post(f"/api/v1/lesson-plans/{plan_id}/sections/examples/regenerate")
            self.assertEqual(regenerated.status_code, 200, regenerated.text)
            self.assertNotEqual(next(section["content"] for section in regenerated.json()["sections"] if section["key"] == "examples"), original)
            self.assertEqual((await client.put(f"/api/v1/lesson-plans/{plan_id}/post-review", json={
                "evaluation": "课堂时态判断仍需巩固", "reflection": "下次增加语境辨析",
            })).status_code, 409)
            await client.post(f"/api/v1/lesson-plans/{plan_id}/submit-review")
            await client.post(f"/api/v1/lesson-plans/{plan_id}/approve")
            review = await client.put(f"/api/v1/lesson-plans/{plan_id}/post-review", json={
                "evaluation": "课堂时态判断仍需巩固", "reflection": "下次增加语境辨析",
            })
            self.assertEqual(review.status_code, 200, review.text)
            overview = (await client.get("/api/v1/classes/1/learning-overview")).json()
            self.assertEqual(overview["teaching_notes"][0]["lesson_plan_id"], plan_id)
            self.assertEqual((await client.delete(f"/api/v1/teaching-goals/{goal_id}")).status_code, 409)

            draft = await client.post("/api/v1/assignment-drafts/generate", json={
                "teaching_goal_id": goal_id, "question_count": 3,
            })
            self.assertEqual(draft.status_code, 201, draft.text)
            self.assertEqual({item["type"] for item in draft.json()["questions"]},
                             {"single_choice", "multiple_choice", "fill_blank"})
            draft_pdf = await client.get(f"/api/v1/assignment-drafts/{draft.json()['id']}/pdf")
            self.assertEqual(draft_pdf.status_code, 200)
            self.assertTrue(draft_pdf.content.startswith(b"%PDF"))
            first = draft.json()["questions"][0]
            edited = await client.patch(f"/api/v1/assignment-drafts/{draft.json()['id']}/questions/{first['id']}", json={
                "stem": "请选出句子中正确的谓语动词形式。",
            })
            self.assertEqual(edited.status_code, 200, edited.text)
            checked = await client.post(f"/api/v1/assignment-drafts/{draft.json()['id']}/questions/{first['id']}/check")
            self.assertEqual(checked.status_code, 200, checked.text)
            self.assertNotEqual(checked.json()["questions"][0]["quality_status"], "needs_revision")
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft.json()['id']}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft.json()['id']}/approve")).status_code, 200)
            assignment_pdf = await client.get(f"/api/v1/assignment-drafts/{draft.json()['id']}/pdf")
            self.assertEqual(assignment_pdf.status_code, 200)
            self.assertTrue(assignment_pdf.content.startswith(b"%PDF"))

            paper = b"1. Fill in the blank: She ___ to school every day.\n2. Fill in the blank: They ___ yesterday."
            key = b"1. goes\n2. played"
            imported = await client.post("/api/v1/assessment-imports", data={"class_id": "1", "title": "Unit test paper"}, files={
                "paper": ("paper.txt", paper, "text/plain"),
                "answer_key": ("answers.txt", key, "text/plain"),
            })
            self.assertEqual(imported.status_code, 201, imported.text)
            import_id = imported.json()["id"]
            self.assertEqual(len(imported.json()["questions"]), 2)
            first_question = imported.json()["questions"][0]
            corrected_question = await client.patch(f"/api/v1/assessment-imports/{import_id}/questions/{first_question['question_id']}", json={
                "stem": "请填入正确的谓语动词：She ___ to school every day.",
                "answer": "goes", "explanation": "第三人称单数用 goes。",
                "knowledge_point_name": "谓语动词",
            })
            self.assertEqual(corrected_question.status_code, 200, corrected_question.text)
            self.assertEqual((await client.post(f"/api/v1/assessment-imports/{import_id}/approve")).status_code, 200)
            self.assertEqual((await client.patch(f"/api/v1/assessment-imports/{import_id}/questions/{first_question['question_id']}", json={
                "stem": "已确认后不能修改", "answer": "goes", "explanation": "教师答案", "knowledge_point_name": "谓语动词",
            })).status_code, 409)
            student_work = await client.post(f"/api/v1/assessment-imports/{import_id}/student-work", data={
                "student_id": "2",
            }, files={"work": ("student.txt", b"1. goes\n2. played", "text/plain")})
            self.assertEqual(student_work.status_code, 201, student_work.text)
            work_id = student_work.json()["works"][0]["id"]
            self.assertEqual(student_work.json()["works"][0]["status"], "pending_review")
            corrected_work = await client.patch(f"/api/v1/assessment-imports/{import_id}/student-work/{work_id}", json={
                "answers": {"1": "goes", "2": "played"},
            })
            self.assertEqual(corrected_work.status_code, 200, corrected_work.text)
            result = await client.post(f"/api/v1/assessment-imports/{import_id}/student-work/{work_id}/confirm")
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["works"][0]["score"], 100)
            self.assertEqual((await client.post(f"/api/v1/assessment-imports/{import_id}/student-work/{work_id}/confirm")).status_code, 409)


if __name__ == "__main__":
    import unittest
    unittest.main()
