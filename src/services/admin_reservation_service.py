from datetime import date, datetime, timedelta
from typing import get_args
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from src.repositories.reservation_repository import ReservationRepository
from src.schemas.admin_reservation import (
    AdminReservationItemResponse,
    AdminReservationListResponse,
    AdminReservationStatusUpdateRequest,
    AdminReservationSummaryResponse,
    ReservationStatus,
)


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
VALID_PERIODS = {"all", "today", "tomorrow", "upcoming"}
VALID_STATUSES = frozenset(get_args(ReservationStatus))

# Maquina de estados do fluxo automatico (quem entra com a chave interna: o n8n,
# ou seja, o botao que o cliente aperta no WhatsApp).
#
#   confirmed --(lembrete enviado)--> reminded --+--> reconfirmed
#                                                +--> cancelled
#
# cancelled, completed e no_show sao terminais: o cliente que responde o lembrete
# tres dias depois, ou aperta o botao de uma reserva ja cancelada, nao reabre
# nada. Admin logado NAO passa por aqui -- correcao de dado na mao continua
# podendo ir de qualquer estado para qualquer estado.
ALLOWED_INTERNAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "confirmed": frozenset({"reminded", "reconfirmed", "cancelled"}),
    "reminded": frozenset({"reconfirmed", "cancelled"}),
    "reconfirmed": frozenset({"cancelled"}),
    "cancelled": frozenset(),
    "completed": frozenset(),
    "no_show": frozenset(),
}


class AdminReservationService:
    def __init__(self, db: Session):
        self.reservation_repo = ReservationRepository(db)

    def update_reservation_status(
        self,
        reservation_id: UUID,
        status_in: AdminReservationStatusUpdateRequest,
        enforce_transition: bool = True,
    ) -> AdminReservationItemResponse:
        reservation = self.reservation_repo.get_admin_reservation_by_id(reservation_id)

        if not reservation:
            raise LookupError("Reserva não encontrada.")

        current_status = reservation.status
        new_status = status_in.status

        # Idempotente de proposito: o cliente aperta o botao duas vezes, a rede
        # repete a chamada, e nada disso pode virar erro para quem chamou.
        if current_status == new_status:
            return self._to_admin_reservation_item(reservation)

        if enforce_transition:
            allowed = ALLOWED_INTERNAL_TRANSITIONS.get(current_status, frozenset())

            if new_status not in allowed:
                raise ValueError(
                    f"Transição de status não permitida: {current_status} → {new_status}."
                )

        updated_reservation = self.reservation_repo.update_status(
            reservation=reservation,
            status=new_status,
        )

        return self._to_admin_reservation_item(updated_reservation)

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
                "Filtro status deve ser um de: "
                + ", ".join(get_args(ReservationStatus))
                + "."
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
            self._to_admin_reservation_item(reservation)
            for reservation in reservations
        ]

        return AdminReservationListResponse(
            summary=AdminReservationSummaryResponse(**summary),
            items=items,
        )

    @staticmethod
    def _to_admin_reservation_item(reservation) -> AdminReservationItemResponse:
        return AdminReservationItemResponse(
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
