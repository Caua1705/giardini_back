from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.reservation_service import ReservationService
from src.schemas.reservation import ReservationCreate, ReservationResponse

router = APIRouter()


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=201,
    summary="Create a reservation",
    description="Creates a reservation for a given environment and customer.",
)
def create_reservation(
    reservation_in: ReservationCreate,
    db: Session = Depends(get_db),
):
    service = ReservationService(db)
    try:
        return service.create_reservation(reservation_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
