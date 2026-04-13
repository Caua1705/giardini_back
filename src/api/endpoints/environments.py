from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.repositories.environment_repository import EnvironmentRepository
from src.schemas.environment import EnvironmentResponse

router = APIRouter()


@router.get(
    "/environments",
    response_model=list[EnvironmentResponse],
    summary="List active environments",
    description="Returns all active environments available for reservation.",
)
def list_environments(db: Session = Depends(get_db)):
    repo = EnvironmentRepository(db)
    try:
        return repo.get_all_active()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
