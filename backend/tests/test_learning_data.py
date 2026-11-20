import asyncio
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.main import app
from app.models import (Assignment, LearningRecord, Question, StudentAnswer,
                        StudentKnowledgeProfile, StudentSubmission)
from app.seed.learning_data import seed_learning_data
from app.services.profile import rebuild_profiles
from support import IsolatedDatabaseTest


class LearningDataTest(IsolatedDatabaseTest):
    def test_seed_and_profile_are_rebuildable(self):
        with self.session_factory() as db:
            seed_learning_data(db)
            seed_learning_data(db)
            self.assertEqual(db.scalar(select(func.count()).select_from(Assignment)), 4)
            self.assertEqual(db.scalar(select(func.count()).select_from(Question)), 20)
            self.assertEqual(db.scalar(select(func.count()).select_from(StudentSubmission)), 24)
            self.assertEqual(db.scalar(select(func.count()).select_from(StudentAnswer)), 120)
            self.assertEqual(db.scalar(select(func.count()).select_from(LearningRecord)), 120)
            before = {(p.student_id, p.knowledge_point_id): (p.accuracy, p.attention_status)
                      for p in db.scalars(select(StudentKnowledgeProfile)).all()}
            rebuild_profiles(db)
            after = {(p.student_id, p.knowledge_point_id): (p.accuracy, p.attention_status)
                     for p in db.scalars(select(StudentKnowledgeProfile)).all()}
            self.assertEqual(before, after)
            self.assertEqual(len(after), 24)

    def test_learning_api(self):
        asyncio.run(self._check_learning_api())

    async def _check_learning_api(self):
        async with self.no_lifespan():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                classroom = (await client.get("/api/v1/classes/1/learning-overview")).json()
                self.assertEqual(classroom["assignment_count"], 4)
                self.assertEqual(classroom["completion_rate"], 1)
                self.assertEqual(len(classroom["knowledge_points"]), 4)
                self.assertGreaterEqual(classroom["attention_students"], 1)

                student = (await client.get("/api/v1/students/1/learning-overview")).json()
                self.assertEqual(student["assignment_count"], 4)
                verb = next(p for p in student["profiles"] if p["knowledge_point"]["name"] == "谓语动词")
                self.assertEqual(verb["attention_status"], "重点关注")
                self.assertEqual(verb["total_attempts"], 8)
                self.assertEqual(verb["correct_count"], 1)
                self.assertEqual(verb["accuracy"], 0.125)
                self.assertTrue(student["records"][0]["answer_text"])

                assignments = (await client.get("/api/v1/assignments?class_id=1")).json()
                self.assertEqual(len(assignments), 4)
                detail = (await client.get(f"/api/v1/assignments/{assignments[0]['id']}")).json()
                self.assertEqual(detail["mode"], "class_unified")
                self.assertEqual(len(detail["questions"]), 5)
                self.assertEqual(len(detail["submissions"]), 6)
                self.assertEqual(len(detail["submissions"][0]["answers"]), 5)
                self.assertEqual((await client.get("/api/v1/assignments/99999")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
