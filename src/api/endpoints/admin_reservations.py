from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies.admin_auth import validate_admin_or_internal
from src.db.session import get_db
from src.models.admin_user_model import AdminUser
from src.schemas.admin_reservation import (
    AdminReservationItemResponse,
    AdminReservationListResponse,
    AdminReservationStatusUpdateRequest,
)
from src.services.admin_reservation_service import AdminReservationService


router = APIRouter(prefix="/admin", tags=["Admin Reservations"])


@router.get(
    "/reservations",
    response_model=AdminReservationListResponse,
    summary="List admin reservations",
    dependencies=[Depends(validate_admin_or_internal)],
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


@router.patch(
    "/reservations/{reservation_id}/status",
    response_model=AdminReservationItemResponse,
    summary="Update admin reservation status",
)
def update_admin_reservation_status(
    reservation_id: UUID,
    status_in: AdminReservationStatusUpdateRequest,
    actor: AdminUser | None = Depends(validate_admin_or_internal),
    db: Session = Depends(get_db),
):
    service = AdminReservationService(db)

    try:
        return service.update_reservation_status(
            reservation_id=reservation_id,
            status_in=status_in,
            # validate_admin_or_internal devolve None quando quem entrou foi a
            # chave interna -- ou seja, o n8n, ou seja, o botao que o cliente
            # apertou. Esse caminho respeita a maquina de estados. Admin logado
            # (AdminUser) corrige dado na mao e passa por cima dela.
            enforce_transition=actor is None,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
