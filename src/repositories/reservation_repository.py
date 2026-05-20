from sqlalchemy import func
from sqlalchemy.orm import Session
from src.models import Client, Environment, Reservation
from uuid import UUID
from datetime import date, time


class ReservationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, reservation_data: dict) -> Reservation:
        db_reservation = Reservation(**reservation_data)
        self.db.add(db_reservation)
        self.db.commit()
        self.db.refresh(db_reservation)
        return db_reservation

    def get_occupied_capacity(
        self,
        environment_id: UUID,
        reservation_date: date,
        reservation_time: time,
    ) -> int:
        """Sums the party_size for all reservations in a specific slot."""
        total = self.db.query(func.sum(Reservation.party_size)).filter(
            Reservation.environment_id == environment_id,
            Reservation.reservation_date == reservation_date,
            Reservation.reservation_time == reservation_time,
        ).scalar()

        return total or 0

    def list_admin_reservations(
        self,
        search: str | None = None,
        reservation_date: date | None = None,
        period: str = "all",
        status: str | None = None,
        environment_id: UUID | None = None,
        today: date | None = None,
        tomorrow: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Reservation]:
        query = self._admin_base_query(
            search=search,
            reservation_date=reservation_date,
            period=period,
            status=status,
            environment_id=environment_id,
            today=today,
            tomorrow=tomorrow,
        )

        return (
            query
            .order_by(
                Reservation.reservation_date.asc(),
                Reservation.reservation_time.asc(),
                Reservation.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_admin_reservations_summary(
        self,
        search: str | None = None,
        reservation_date: date | None = None,
        period: str = "all",
        status: str | None = None,
        environment_id: UUID | None = None,
        today: date | None = None,
        tomorrow: date | None = None,
    ) -> dict[str, int]:
        query = self._admin_base_query(
            search=search,
            reservation_date=reservation_date,
            period=period,
            status=status,
            environment_id=environment_id,
            today=today,
            tomorrow=tomorrow,
        )

        reservations = query.all()

        total_reservations = len(reservations)

        today_reservations = sum(
            1
            for reservation in reservations
            if reservation.reservation_date == today
        )

        total_guests = sum(
            reservation.party_size
            for reservation in reservations
        )

        upcoming_reservations = sum(
            1
            for reservation in reservations
            if reservation.reservation_date >= today
            and reservation.status != "cancelled"
        )

        return {
            "total_reservations": total_reservations,
            "today_reservations": today_reservations,
            "total_guests": total_guests,
            "upcoming_reservations": upcoming_reservations,
        }

    def _admin_base_query(
        self,
        search: str | None = None,
        reservation_date: date | None = None,
        period: str = "all",
        status: str | None = None,
        environment_id: UUID | None = None,
        today: date | None = None,
        tomorrow: date | None = None,
    ):
        query = (
            self.db.query(Reservation)
            .join(Client, Reservation.client_id == Client.id)
            .join(Environment, Reservation.environment_id == Environment.id)
        )

        if search:
            search = search.strip()

            query = query.filter(
                Client.name.contains(search)
                | Client.email.contains(search)
                | Client.phone.contains(search)
            )

        if reservation_date:
            query = query.filter(Reservation.reservation_date == reservation_date)

        if period == "today":
            query = query.filter(Reservation.reservation_date == today)

        if period == "tomorrow":
            query = query.filter(Reservation.reservation_date == tomorrow)

        if period == "upcoming":
            query = query.filter(Reservation.reservation_date >= today)

        if status:
            query = query.filter(Reservation.status == status)

        if environment_id:
            query = query.filter(Reservation.environment_id == environment_id)

        return query