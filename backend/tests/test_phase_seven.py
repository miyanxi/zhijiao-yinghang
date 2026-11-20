import asyncio
import os
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from support import IsolatedDatabaseTest


class PhaseSevenWorkflowTest(IsolatedDatabaseTest):
    """Run the competition demo story against a fresh, isolated SQLite database."""

    def test_complete_teaching_learning_intervention_loop(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "1"}):
            asyncio.run(self._workflow())

    async def _workflow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            original_class = (await client.get("/api/v1/classes/1/learning-overview")).json()

            parsed = await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1,
                "raw_input": "复习谓语动词和一般过去时，完成班级统一练习。",
            })
            self.assertEqual(parsed.status_code, 200, parsed.text)
            self.assertEqual(parsed.json()["source"], "demo")
            goal = await client.post("/api/v1/teaching-goals", json=parsed.json() | {
                "class_id": 1,
                "raw_input": "复习谓语动词和一般过去时，完成班级统一练习。",
            })
            self.assertEqual(goal.status_code, 201, goal.text)
            goal_id = goal.json()["id"]
            self.assertEqual((await client.post("/api/v1/lesson-plans/generate", json={
                "teaching_goal_id": goal_id,
            })).status_code, 409)
            confirmed_goal = await client.post(f"/api/v1/teaching-goals/{goal_id}/confirm")
            self.assertEqual(confirmed_goal.status_code, 200, confirmed_goal.text)

            lesson = await client.post("/api/v1/lesson-plans/generate", json={
                "teaching_goal_id": goal_id,
            })
            self.assertEqual(lesson.status_code, 201, lesson.text)
            self.assertEqual(lesson.json()["status"], "draft")
            plan_id = lesson.json()["id"]
            self.assertEqual((await client.post(f"/api/v1/lesson-plans/{plan_id}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/lesson-plans/{plan_id}/approve")).status_code, 200)

            draft = await client.post("/api/v1/assignment-drafts/generate", json={
                "teaching_goal_id": goal_id,
                "question_count": 3,
            })
            self.assertEqual(draft.status_code, 201, draft.text)
            draft_id = draft.json()["id"]
            self.assertEqual(draft.json()["mode"], "class_unified")
            self.assertEqual((await client.post(f"/api/v1/assignments/publish/{draft_id}")).status_code, 409)
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft_id}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft_id}/approve")).status_code, 200)
            published = await client.post(f"/api/v1/assignments/publish/{draft_id}")
            self.assertEqual(published.status_code, 201, published.text)
            assignment_id = published.json()["id"]

            detail = (await client.get(f"/api/v1/assignments/{assignment_id}")).json()
            correct_answers = [{"question_id": q["question_id"], "answer_text": q["answer"]} for q in detail["questions"]]
            student_ids = [student["id"] for student in (await client.get("/api/v1/classes/1/students")).json()]
            first = await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[1], "answers": correct_answers,
            })
            self.assertEqual(first.status_code, 201, first.text)
            self.assertEqual(first.json()["total_score"], 100)
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[1], "answers": correct_answers,
            })).status_code, 409)
            overview_after_one = (await client.get("/api/v1/classes/1/learning-overview")).json()
            self.assertEqual(overview_after_one["assignment_count"], original_class["assignment_count"] + 1)
            expected_rate = (original_class["completion_rate"] * original_class["assignment_count"] + 1 / len(student_ids)) / (original_class["assignment_count"] + 1)
            self.assertAlmostEqual(overview_after_one["completion_rate"], expected_rate)

            candidate_response = await client.get("/api/v1/targeted-trainings/candidates?class_id=1")
            self.assertEqual(candidate_response.status_code, 200, candidate_response.text)
            candidate = next(item for item in candidate_response.json()
                             if item["student_name"] == "张同学" and item["knowledge_point_name"] == "谓语动词")
            confirmation = await client.post("/api/v1/targeted-trainings/confirm", json={
                "student_id": candidate["student_id"],
                "knowledge_point_id": candidate["knowledge_point_id"],
            })
            self.assertEqual(confirmation.status_code, 201, confirmation.text)
            training_id = confirmation.json()["id"]
            generated = await client.post(f"/api/v1/targeted-trainings/{training_id}/generate")
            self.assertEqual(generated.status_code, 200, generated.text)
            self.assertEqual(generated.json()["status"], "draft")
            for question in generated.json()["questions"]:
                checked = await client.post(f"/api/v1/targeted-trainings/{training_id}/questions/{question['order_no']}/check")
                self.assertEqual(checked.status_code, 200, checked.text)
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/approve")).status_code, 200)
            training = await client.post(f"/api/v1/targeted-trainings/{training_id}/publish")
            self.assertEqual(training.status_code, 200, training.text)
            training_assignment_id = training.json()["assignment_id"]
            training_detail = (await client.get(f"/api/v1/assignments/{training_assignment_id}")).json()
            training_answers = [{"question_id": q["question_id"], "answer_text": q["answer"]}
                                for q in training_detail["questions"]]
            result = await client.post(f"/api/v1/assignments/{training_assignment_id}/submissions", json={
                "student_id": candidate["student_id"], "answers": training_answers,
            })
            self.assertEqual(result.status_code, 201, result.text)
            self.assertEqual(result.json()["total_score"], 100)
            completed = (await client.get(f"/api/v1/targeted-trainings/{training_id}")).json()
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["training_accuracy"], 1)

            final_class = (await client.get("/api/v1/classes/1/learning-overview")).json()
            self.assertEqual(final_class["assignment_count"], original_class["assignment_count"] + 1)
            self.assertAlmostEqual(final_class["completion_rate"], expected_rate)
            student = (await client.get(f"/api/v1/students/{candidate['student_id']}/learning-overview")).json()
            self.assertTrue(any(record["assignment_id"] == training_assignment_id for record in student["records"]))


if __name__ == "__main__":
    import unittest

    unittest.main()
