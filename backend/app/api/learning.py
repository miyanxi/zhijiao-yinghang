from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.learning import ClassLearningOverview, StudentLearningOverview
from ..services.learning_queries import class_learning_overview, student_learning_overview

router = APIRouter(tags=["learning-data"])


@router.get("/classes/{class_id}/learning-overview", response_model=ClassLearningOverview)
def get_class_learning_overview(class_id: int, db: Session = Depends(get_db)) -> ClassLearningOverview:
    return class_learning_overview(class_id, db)


@router.get("/students/{student_id}/learning-overview", response_model=StudentLearningOverview)
def get_student_learning_overview(student_id: int, db: Session = Depends(get_db)) -> StudentLearningOverview:
    return student_learning_overview(student_id, db)
