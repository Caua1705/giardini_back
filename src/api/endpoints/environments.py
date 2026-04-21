from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.environment_service import EnvironmentService
from src.schemas.environment import EnvironmentResponse

router = APIRouter()


@router.get(
    "/environments",
    response_model=list[EnvironmentResponse],
    summary="List active environments",
    description="Returns all active environments available for reservation.",
)
def list_environments(db: Session = Depends(get_db)):
    service = EnvironmentService(db)
    return service.get_active_environments()
