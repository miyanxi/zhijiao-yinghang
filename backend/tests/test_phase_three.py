import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base
from app.seed.demo_data import seed_demo_data
from app.seed.learning_data import seed_learning_data


class PhaseThreeTest(unittest.TestCase):
    def setUp(self):
        self.previous_key = os.environ.get("DEEPSEEK_API_KEY")
        self.previous_demo = os.environ.get("ENABLE_TEST_DEMO_GENERATION")
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ["ENABLE_TEST_DEMO_GENERATION"] = "1"
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as db:
            seed_demo_data(db)
            seed_learning_data(db)

        def test_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = test_db

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()
        if self.previous_key is not None:
            os.environ["DEEPSEEK_API_KEY"] = self.previous_key
        if self.previous_demo is None:
            os.environ.pop("ENABLE_TEST_DEMO_GENERATION", None)
        else:
            os.environ["ENABLE_TEST_DEMO_GENERATION"] = self.previous_demo

    def test_teacher_management_and_phase_three_workflow(self):
        asyncio.run(self._workflow())

    def test_phase_four_publication_grading_and_trend(self):
        asyncio.run(self._phase_four())

    async def _phase_four(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            original = (await client.get("/api/v1/classes/1/learning-overview")).json()
            parsed = (await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "复习谓语动词和一般过去时，完成统一练习。",
            })).json()
            goal = (await client.post("/api/v1/teaching-goals", json=parsed | {
                "class_id": 1, "raw_input": "复习谓语动词和一般过去时，完成统一练习。",
            })).json()
            await client.post(f"/api/v1/teaching-goals/{goal['id']}/confirm")
            draft = (await client.post("/api/v1/assignment-drafts/generate", json={
                "teaching_goal_id": goal["id"], "question_count": 3,
            })).json()
            draft_id = draft["id"]
            self.assertEqual((await client.post(f"/api/v1/assignments/publish/{draft_id}")).status_code, 409)
            await client.post(f"/api/v1/assignment-drafts/{draft_id}/submit-review")
            await client.post(f"/api/v1/assignment-drafts/{draft_id}/approve")
            publication = await client.post(f"/api/v1/assignments/publish/{draft_id}")
            self.assertEqual(publication.status_code, 201, publication.text)
            assignment_id = publication.json()["id"]
            self.assertEqual(publication.json()["status"], "published")
            self.assertEqual(publication.json()["source_draft_id"], draft_id)
            self.assertEqual((await client.post(f"/api/v1/assignments/publish/{draft_id}")).status_code, 409)
            self.assertEqual((await client.patch(f"/api/v1/assignment-drafts/{draft_id}/questions/{draft['questions'][0]['id']}", json={"stem": "发布后不可修改"})).status_code, 409)
            detail = (await client.get(f"/api/v1/assignments/{assignment_id}")).json()
            self.assertEqual(len(detail["questions"]), 3)
            self.assertAlmostEqual(sum(item.score for item in self._assignment_scores(assignment_id)), 100)
            student_ids = [item["id"] for item in (await client.get("/api/v1/classes/1/students")).json()]
            answers = [{"question_id": item["question_id"], "answer_text": item["answer"]} for item in detail["questions"]]
            other_class = (await client.post("/api/v1/classes", json={"name": "高一测试班", "grade": "高一"})).json()
            outsider = (await client.post(f"/api/v1/classes/{other_class['id']}/students", json={"name": "外班学生", "student_no": "X001"})).json()
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": outsider["id"], "answers": answers,
            })).status_code, 422)
            invalid = [item.copy() for item in answers]
            invalid[0]["answer_text"] = "not an option"
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[0], "answers": invalid,
            })).status_code, 422)
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[0], "answers": answers[:2],
            })).status_code, 422)
            first = await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[0], "answers": answers,
            })
            self.assertEqual(first.status_code, 201, first.text)
            self.assertEqual(first.json()["total_score"], 100)
            self.assertEqual((await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[0], "answers": answers,
            })).status_code, 409)
            wrong = answers.copy()
            wrong[0] = {"question_id": answers[0]["question_id"], "answer_text": next(option for option in detail["questions"][0]["options"] if option != answers[0]["answer_text"])}
            second = await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                "student_id": student_ids[1], "answers": wrong,
            })
            self.assertEqual(second.status_code, 201, second.text)
            self.assertFalse(second.json()["answers"][0]["is_correct"])
            self.assertEqual(second.json()["answers"][0]["score"], 0)
            updated = (await client.get("/api/v1/classes/1/learning-overview")).json()
            self.assertEqual(updated["assignment_count"], original["assignment_count"] + 1)
            self.assertEqual(updated["score_trend"][-1]["submission_count"], 2)
            self.assertEqual(updated["error_count"], original["error_count"] + 1)
            student_trend = (await client.get(f"/api/v1/students/{student_ids[1]}/learning-overview")).json()
            self.assertEqual(student_trend["score_trend"][-1]["assignment_id"], assignment_id)
            self.assertTrue(any(record["assignment_id"] == assignment_id and not record["is_correct"] for record in student_trend["records"]))
            for student_id in student_ids[2:]:
                response = await client.post(f"/api/v1/assignments/{assignment_id}/submissions", json={
                    "student_id": student_id, "answers": answers,
                })
                self.assertEqual(response.status_code, 201, response.text)
            finished = (await client.get(f"/api/v1/assignments/{assignment_id}")).json()
            self.assertEqual(finished["status"], "analyzed")
            self.assertEqual(finished["submission_count"], 6)
            self.assertEqual((await client.get("/api/v1/classes/1/learning-overview")).json()["completion_rate"], 1)

    def _assignment_scores(self, assignment_id):
        from sqlalchemy import select
        from app.models import AssignmentQuestion
        with self.session_factory() as db:
            return db.scalars(select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment_id)).all()

    async def _workflow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            classroom = await client.post("/api/v1/classes", json={"name": "高一（4）班", "grade": "高一"})
            self.assertEqual(classroom.status_code, 201, classroom.text)
            class_id = classroom.json()["id"]
            student = await client.post(f"/api/v1/classes/{class_id}/students", json={"name": "周同学", "student_no": "G1-401"})
            self.assertEqual(student.status_code, 201, student.text)
            self.assertEqual((await client.get(f"/api/v1/classes/{class_id}")).json()["students"][0]["name"], "周同学")
            self.assertEqual((await client.post(f"/api/v1/classes/{class_id}/students", json={"name": "重复", "student_no": "G1-401"})).status_code, 409)
            self.assertEqual((await client.patch(f"/api/v1/students/{student.json()['id']}", json={"name": "周老师的学生"})).status_code, 200)
            self.assertEqual((await client.patch(f"/api/v1/classes/{class_id}", json={"current_topic": "谓语动词"})).status_code, 200)

            parsed = await client.post("/api/v1/teaching-goals/parse", json={
                "class_id": 1, "raw_input": "这周讲谓语动词和一般过去时，基础差异较大。",
            })
            self.assertEqual(parsed.status_code, 200, parsed.text)
            self.assertEqual(parsed.json()["source"], "demo")
            payload = parsed.json() | {"class_id": 1, "raw_input": "这周讲谓语动词和一般过去时，基础差异较大。"}
            goal = await client.post("/api/v1/teaching-goals", json=payload)
            self.assertEqual(goal.status_code, 201, goal.text)
            goal_id = goal.json()["id"]
            self.assertEqual((await client.post("/api/v1/lesson-plans/generate", json={"teaching_goal_id": goal_id})).status_code, 409)
            self.assertEqual((await client.patch(f"/api/v1/teaching-goals/{goal_id}", json={"key_points": "教师修订后的重点"})).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/teaching-goals/{goal_id}/confirm")).status_code, 200)
            self.assertEqual((await client.patch(f"/api/v1/teaching-goals/{goal_id}", json={"topic": "不可修改"})).status_code, 409)

            plan = await client.post("/api/v1/lesson-plans/generate", json={"teaching_goal_id": goal_id, "duration_minutes": 45})
            self.assertEqual(plan.status_code, 201, plan.text)
            plan_id = plan.json()["id"]
            self.assertEqual(len(plan.json()["sections"]), 12)
            before_sections = {item["key"]: item["content"] for item in plan.json()["sections"]}
            edited = await client.patch(f"/api/v1/lesson-plans/{plan_id}/sections/examples", json={"content": "教师修改的示例", "duration_minutes": 6})
            self.assertEqual(edited.status_code, 200, edited.text)
            after_sections = {item["key"]: item["content"] for item in edited.json()["sections"]}
            self.assertEqual(after_sections["examples"], "教师修改的示例")
            self.assertEqual(after_sections["objectives"], before_sections["objectives"])
            self.assertEqual((await client.post(f"/api/v1/lesson-plans/{plan_id}/sections/examples/regenerate")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/lesson-plans/{plan_id}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/lesson-plans/{plan_id}/approve")).status_code, 200)
            self.assertEqual((await client.patch(f"/api/v1/lesson-plans/{plan_id}", json={"title": "不可修改"})).status_code, 409)

            published_before = (await client.get("/api/v1/assignments?class_id=1")).json()
            learning_before = (await client.get("/api/v1/classes/1/learning-overview")).json()
            draft = await client.post("/api/v1/assignment-drafts/generate", json={"teaching_goal_id": goal_id, "question_count": 5})
            self.assertEqual(draft.status_code, 201, draft.text)
            draft_id = draft.json()["id"]
            self.assertEqual(draft.json()["mode"], "class_unified")
            self.assertEqual(draft.json()["source"], "demo")
            self.assertTrue(all(item["quality_status"] == "demo_checked" for item in draft.json()["questions"]))
            question_id = draft.json()["questions"][0]["id"]
            edited = await client.patch(f"/api/v1/assignment-drafts/{draft_id}/questions/{question_id}", json={"stem": "She ___ to school every morning after breakfast."})
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["questions"][0]["quality_status"], "unchecked")
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft_id}/submit-review")).status_code, 409)
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft_id}/questions/{question_id}/check")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft_id}/submit-review")).status_code, 200)
            self.assertEqual((await client.post(f"/api/v1/assignment-drafts/{draft_id}/approve")).status_code, 200)
            self.assertEqual((await client.patch(f"/api/v1/assignment-drafts/{draft_id}/questions/{question_id}", json={"stem": "这道题已经审核，不允许修改。"})).status_code, 409)
            self.assertEqual(len((await client.get("/api/v1/assignments?class_id=1")).json()), len(published_before))
            self.assertEqual((await client.get("/api/v1/classes/1/learning-overview")).json(), learning_before)


if __name__ == "__main__":
    unittest.main()
