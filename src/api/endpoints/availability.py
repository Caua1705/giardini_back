from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from src.db.session import get_db
from src.services.reservation_service import ReservationService

router = APIRouter()


@router.get("/availability")
def get_availability(
    environment_id: str,
    reservation_date: date,
    party_size: int,
    db: Session = Depends(get_db),
):
    service = ReservationService(db)

    return service.get_available_times(
        environment_id=environment_id,
        reservation_date=reservation_date,
        party_size=party_size,
    )