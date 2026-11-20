from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.manager import ManagerRequest, ManagerResponse
from ..services.ai_service import AIServiceError
from ..services.manager import handle_manager_request

router = APIRouter(prefix="/manager", tags=["manager"])


@router.post("/interpret", response_model=ManagerResponse)
def interpret_request(payload: ManagerRequest, db: Session = Depends(get_db)) -> ManagerResponse:
    try:
        return handle_manager_request(payload, db)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
