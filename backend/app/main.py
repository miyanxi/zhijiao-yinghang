from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .api import (assessment_imports, assignment_drafts, assignments, classes,
                  learning, lesson_plans, manager, students, targeted_trainings,
                  teaching_goals)
from .api import assignment_uploads
from .database import SessionLocal, get_db, init_db
from .schemas.base import HealthRead
from .seed.demo_data import seed_demo_data
from .seed.learning_data import seed_learning_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_demo_data(db)
        seed_learning_data(db)
    yield


app = FastAPI(title="智教英航 API", version="0.1.0", lifespan=lifespan)
public_origin = os.getenv("FRONTEND_ORIGIN", "").strip().rstrip("/")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_origins=[public_origin] if public_origin else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", response_model=HealthRead, tags=["system"])
def health(db: Session = Depends(get_db)) -> HealthRead:
    db.execute(text("SELECT 1"))
    return HealthRead(status="ok", database="ok")


app.include_router(classes.router, prefix="/api/v1")
app.include_router(students.router, prefix="/api/v1")
app.include_router(learning.router, prefix="/api/v1")
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(assessment_imports.router, prefix="/api/v1")
app.include_router(teaching_goals.router, prefix="/api/v1")
app.include_router(lesson_plans.router, prefix="/api/v1")
app.include_router(assignment_drafts.router, prefix="/api/v1")
app.include_router(assignment_uploads.router, prefix="/api/v1")
app.include_router(targeted_trainings.router, prefix="/api/v1")
app.include_router(manager.router, prefix="/api/v1")

FRONTEND_DIST = os.getenv("ZHJ_FRONTEND_DIST", "")
if FRONTEND_DIST and os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = os.path.join(FRONTEND_DIST, path)
        if path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
