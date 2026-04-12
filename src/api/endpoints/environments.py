from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.repositories.environment_repository import EnvironmentRepository
from src.schemas.environment import EnvironmentResponse

router = APIRouter()


@router.get("/environments", response_model=list[EnvironmentResponse])
def list_environments(db: Session = Depends(get_db)):
    repo = EnvironmentRepository(db)
    return repo.get_all_active()