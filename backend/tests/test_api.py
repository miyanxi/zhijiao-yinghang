import asyncio
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.main import app
from app.models import Class, Student, Teacher
from app.seed.demo_data import seed_demo_data
from support import IsolatedDatabaseTest


class PhaseOneApiTest(IsolatedDatabaseTest):
    def test_phase_one_api_contract(self):
        asyncio.run(self._check_api())

    async def _check_api(self):
        async with self.no_lifespan():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                health = await client.get("/api/v1/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json(), {"status": "ok", "database": "ok"})

                classes = await client.get("/api/v1/classes")
                self.assertEqual(classes.status_code, 200)
                self.assertEqual(len(classes.json()), 1)
                class_id = classes.json()[0]["id"]

                class_detail = await client.get(f"/api/v1/classes/{class_id}")
                self.assertEqual(class_detail.status_code, 200)
                self.assertEqual(len(class_detail.json()["students"]), 6)

                students = await client.get(f"/api/v1/classes/{class_id}/students")
                self.assertEqual(students.status_code, 200)
                student_id = students.json()[0]["id"]

                student = await client.get(f"/api/v1/students/{student_id}")
                self.assertEqual(student.status_code, 200)
                self.assertEqual(student.json()["class_id"], class_id)

                self.assertEqual((await client.get("/api/v1/classes/99999")).status_code, 404)
                self.assertEqual((await client.get("/api/v1/classes/99999/students")).status_code, 404)
                self.assertEqual((await client.get("/api/v1/students/99999")).status_code, 404)

    def test_seed_is_idempotent(self):
        with self.session_factory() as db:
            seed_demo_data(db)
            seed_demo_data(db)
            self.assertEqual(db.scalar(select(func.count()).select_from(Teacher)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Class)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Student)), 6)


if __name__ == "__main__":
    unittest.main()

