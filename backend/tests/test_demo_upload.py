import asyncio
import os
from io import BytesIO
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter

from app.main import app
from support import IsolatedDatabaseTest


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class DemoUploadTest(IsolatedDatabaseTest):
    def test_demo_upload_is_labeled_and_requires_confirmation(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ENABLE_TEST_DEMO_GENERATION": "1", "ZHJ_DEMO_UPLOAD": "1"}):
            asyncio.run(self.workflow())

    async def workflow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            parsed = (await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "复习一般现在时和一般过去时的区别。",
            })).json()
            goal = (await client.post("/api/v1/teaching-goals", json=parsed | {
                "class_id": 1, "raw_input": "复习一般现在时和一般过去时的区别。",
            })).json()
            await client.post(f"/api/v1/teaching-goals/{goal['id']}/confirm")
            draft = (await client.post("/api/v1/assignment-drafts/generate", json={
                "teaching_goal_id": goal["id"], "question_count": 3,
            })).json()
            await client.post(f"/api/v1/assignment-drafts/{draft['id']}/submit-review")
            await client.post(f"/api/v1/assignment-drafts/{draft['id']}/approve")
            published = await client.post(f"/api/v1/assignments/publish/{draft['id']}")
            self.assertEqual(published.status_code, 201, published.text)
            assignment_id = published.json()["id"]
            students = (await client.get("/api/v1/classes/1/students")).json()
            zhang = next(item for item in students if item["student_no"] == "G1-001")
            other = next(item for item in students if item["student_no"] == "G1-002")
            before = (await client.get(f"/api/v1/students/{zhang['id']}/learning-overview")).json()
            pdf = blank_pdf()

            invalid = await client.post(f"/api/v1/assignments/{assignment_id}/student-works",
                                        data={"student_id": str(zhang["id"])},
                                        files={"work": ("work.pdf", b"not a pdf", "application/pdf")})
            self.assertEqual(invalid.status_code, 422)
            other_upload = await client.post(f"/api/v1/assignments/{assignment_id}/student-works",
                                             data={"student_id": str(other["id"])},
                                             files={"work": ("work.pdf", pdf, "application/pdf")})
            self.assertEqual(other_upload.status_code, 422)

            uploaded = await client.post(f"/api/v1/assignments/{assignment_id}/student-works",
                                         data={"student_id": str(zhang["id"])},
                                         files={"work": ("zhang-work.pdf", pdf, "application/pdf")})
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            self.assertTrue(uploaded.json()["demo_upload_enabled"])
            work = uploaded.json()["works"][0]
            self.assertTrue(work["demo_simulated"])
            self.assertEqual(work["status"], "pending_review")
            self.assertIsNone(work["score"])
            duplicate = await client.post(f"/api/v1/assignments/{assignment_id}/student-works",
                                          data={"student_id": str(zhang["id"])},
                                          files={"work": ("zhang-work.pdf", pdf, "application/pdf")})
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual((await client.get(f"/api/v1/students/{zhang['id']}/learning-overview")).json()["assignment_count"], before["assignment_count"])

            confirmed = await client.post(f"/api/v1/assignments/{assignment_id}/student-works/{work['id']}/confirm")
            self.assertEqual(confirmed.status_code, 200, confirmed.text)
            self.assertTrue(confirmed.json()["works"][0]["demo_simulated"])
            self.assertIsNotNone(confirmed.json()["works"][0]["score"])
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/student-works/{work['id']}/confirm")).status_code, 404)
            after = (await client.get(f"/api/v1/students/{zhang['id']}/learning-overview")).json()
            self.assertEqual(after["assignment_count"], before["assignment_count"] + 1)
            self.assertTrue(any(item["assignment_id"] == assignment_id and item["demo_simulated"] for item in after["records"]))
            before_attempts = sum(item["total_attempts"] for item in before["profiles"])
            after_attempts = sum(item["total_attempts"] for item in after["profiles"])
            self.assertEqual(after_attempts, before_attempts + len(draft["questions"]))
            classroom = (await client.get("/api/v1/classes/1/learning-overview")).json()
            self.assertEqual(classroom["demo_submission_count"], 1)

    def test_demo_mode_off_does_not_accept_blank_pdf_as_answers(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "ZHJ_DEMO_UPLOAD": "0"}):
            asyncio.run(self.disabled_upload())

    async def disabled_upload(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/assignments/1/student-works")
            self.assertFalse(response.json()["demo_upload_enabled"])
