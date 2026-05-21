from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from src.repositories.reservation_repository import ReservationRepository
from src.schemas.admin_reservation import (
    AdminReservationItemResponse,
    AdminReservationListResponse,
    AdminReservationSummaryResponse,
)


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
VALID_PERIODS = {"all", "today", "tomorrow", "upcoming"}
VALID_STATUSES = {"confirmed", "cancelled", "completed", "no_show"}


class AdminReservationService:
    def __init__(self, db: Session):
        self.reservation_repo = ReservationRepository(db)

    def list_reservations(
        self,
        search: str | None = None,
        reservation_date: date | None = None,
        period: str = "all",
        status: str | None = None,
        environment_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AdminReservationListResponse:
        period = period.strip().lower()

        if period not in VALID_PERIODS:
            raise ValueError("Filtro period deve ser: all, today, tomorrow ou upcoming.")

        today = datetime.now(SAO_PAULO_TZ).date()
        tomorrow = today + timedelta(days=1)

        search = search.strip() if search and search.strip() else None
        status = status.strip() if status and status.strip() else None

        if status and status not in VALID_STATUSES:
            raise ValueError(
                "Filtro status deve ser: confirmed, cancelled, completed ou no_show."
            )

        summary = self.reservation_repo.get_admin_reservations_summary(
            search=search,
            reservation_date=reservation_date,
            period=period,
            status=status,
            environment_id=environment_id,
            today=today,
            tomorrow=tomorrow,
        )

        reservations = self.reservation_repo.list_admin_reservations(
            search=search,
            reservation_date=reservation_date,
            period=period,
            status=status,
            environment_id=environment_id,
            today=today,
            tomorrow=tomorrow,
            limit=limit,
            offset=offset,
        )

        items = [
            AdminReservationItemResponse(
                id=reservation.id,
                reservation_date=reservation.reservation_date,
                reservation_time=reservation.reservation_time,
                party_size=reservation.party_size,
                status=reservation.status,
                notes=reservation.notes,
                created_at=reservation.created_at,
                client_id=reservation.client.id,
                client_name=reservation.client.name,
                client_email=reservation.client.email,
                client_phone=reservation.client.phone,
                environment_id=reservation.environment.id,
                environment_name=reservation.environment.name,
                environment_max_capacity=reservation.environment.max_capacity,
            )
            for reservation in reservations
        ]

        return AdminReservationListResponse(
            summary=AdminReservationSummaryResponse(**summary),
            items=items,
        )
