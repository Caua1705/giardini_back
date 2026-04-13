from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from src.db.session import get_db
from src.schemas.availability import AvailabilityResponse
from src.services.reservation_service import ReservationService

router = APIRouter()


@router.get(
    "/availability",
    response_model=list[AvailabilityResponse],
    summary="Get available reservation times",
    description="Returns available time slots based on environment, date and party size.",
)
def get_availability(
    environment_id: str,
    reservation_date: date,
    party_size: int,
    db: Session = Depends(get_db),
):
    service = ReservationService(db)
    try:
        times = service.get_available_times(
            environment_id=environment_id,
            reservation_date=reservation_date,
            party_size=party_size,
        )
        return [AvailabilityResponse(time=t) for t in times]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
