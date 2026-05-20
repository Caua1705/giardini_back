from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies.admin_auth import get_current_admin_user
from src.db.session import get_db
from src.schemas.admin_reservation import AdminReservationListResponse
from src.services.admin_reservation_service import AdminReservationService


router = APIRouter(prefix="/admin", tags=["Admin Reservations"])


@router.get(
    "/reservations",
    response_model=AdminReservationListResponse,
    summary="List admin reservations",
    dependencies=[Depends(get_current_admin_user)],
)
def list_admin_reservations(
    search: str | None = None,
    reservation_date: date | None = Query(default=None, alias="date"),
    period: str = "all",
    status: str | None = None,
    environment_id: UUID | None = None,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    service = AdminReservationService(db)

    try:
        return service.list_reservations(
            search=search,
            reservation_date=reservation_date,
            period=period,
            status=status,
            environment_id=environment_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))