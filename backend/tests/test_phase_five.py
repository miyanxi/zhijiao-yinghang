import asyncio
import os
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from support import IsolatedDatabaseTest


class PhaseFiveTest(IsolatedDatabaseTest):
    def test_targeted_training_requires_teacher_and_updates_profile(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "1"}):
            asyncio.run(self._workflow())

    async def _workflow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            candidates_response = await client.get("/api/v1/targeted-trainings/candidates?class_id=1")
            self.assertEqual(candidates_response.status_code, 200)
            candidate = next(item for item in candidates_response.json() if item["student_name"] == "张同学" and item["knowledge_point_name"] == "谓语动词")
            original_class = (await client.get("/api/v1/classes/1/learning-overview")).json()
            original_student = (await client.get(f"/api/v1/students/{candidate['student_id']}/learning-overview")).json()
            self.assertEqual((await client.post("/api/v1/targeted-trainings/confirm", json={
                "student_id": 6, "knowledge_point_id": candidate["knowledge_point_id"],
            })).status_code, 409)
            confirmation = await client.post("/api/v1/targeted-trainings/confirm", json={
                "student_id": candidate["student_id"], "knowledge_point_id": candidate["knowledge_point_id"],
                "question_count": 10, "duration_minutes": 15,
            })
            self.assertEqual(confirmation.status_code, 201, confirmation.text)
            training = confirmation.json()
            training_id = training["id"]
            self.assertEqual(training["status"], "confirmed")
            self.assertEqual((await client.post("/api/v1/targeted-trainings/confirm", json={
                "student_id": candidate["student_id"], "knowledge_point_id": candidate["knowledge_point_id"],
            })).status_code, 409)
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/publish")).status_code, 409)
            generated = await client.post(f"/api/v1/targeted-trainings/{training_id}/generate")
            self.assertEqual(generated.status_code, 200, generated.text)
            self.assertEqual(generated.json()["source"], "demo")
            self.assertEqual(len(generated.json()["questions"]), 10)
            self.assertTrue(all(item["knowledge_point_id"] == candidate["knowledge_point_id"] for item in generated.json()["questions"]))
            first = generated.json()["questions"][0]
            edit = await client.patch(f"/api/v1/targeted-trainings/{training_id}/questions/1", json={
                "stem": first["stem"], "options": first["options"], "answer": first["answer"],
                "explanation": "教师核对过的解析。", "difficulty": "基础",
            })
            self.assertEqual(edit.status_code, 200, edit.text)
            self.assertEqual(edit.json()["questions"][0]["quality_status"], "unchecked")
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/submit-review")).status_code, 409)
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/questions/1/check")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/approve")).status_code, 200)
            publication = await client.post(f"/api/v1/targeted-trainings/{training_id}/publish")
            self.assertEqual(publication.status_code, 200, publication.text)
            assignment_id = publication.json()["assignment_id"]
            self.assertEqual((await client.post(f"/api/v1/targeted-trainings/{training_id}/publish")).status_code, 409)
            detail = (await client.get(f"/api/v1/assignments/{assignment_id}")).json()
            self.assertEqual(detail["mode"], "targeted_training")
            answers = [{"question_id": item["question_id"], "answer_text": item["answer"]} for item in detail["questions"]]
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": 2, "answers": answers,
            })).status_code, 403)
            submitted = await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": candidate["student_id"], "answers": answers,
            })
            self.assertEqual(submitted.status_code, 201, submitted.text)
            self.assertEqual(submitted.json()["total_score"], 100)
            result = (await client.get(f"/api/v1/targeted-trainings/{training_id}")).json()
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["training_accuracy"], 1)
            self.assertEqual(result["baseline_recent_accuracy"], training["baseline_recent_accuracy"])
            self.assertGreater(result["current_recent_accuracy"], result["baseline_recent_accuracy"])
            updated_student = (await client.get(f"/api/v1/students/{candidate['student_id']}/learning-overview")).json()
            self.assertEqual(updated_student["assignment_count"], original_student["assignment_count"])
            self.assertTrue(any(record["assignment_id"] == assignment_id for record in updated_student["records"]))
            updated_class = (await client.get("/api/v1/classes/1/learning-overview")).json()
            for field in ("assignment_count", "average_score", "completion_rate", "knowledge_points", "error_count", "score_trend"):
                self.assertEqual(updated_class[field], original_class[field])
            self.assertLessEqual(updated_class["attention_students"], original_class["attention_students"])
