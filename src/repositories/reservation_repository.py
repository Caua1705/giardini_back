from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from src.models import Client, Environment, Reservation
from src.core.constants import RESERVATION_DURATION_HOURS
from uuid import UUID
from datetime import date, time, datetime, timedelta


class ReservationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, reservation_data: dict) -> Reservation:
        db_reservation = Reservation(**reservation_data)
        self.db.add(db_reservation)
        self.db.commit()
        self.db.refresh(db_reservation)
        return db_reservation

    def get_admin_reservation_by_id(self, reservation_id: UUID) -> Reservation | None:
        return (
            self.db.query(Reservation)
            .options(
                joinedload(Reservation.client),
                joinedload(Reservation.environment),
            )
            .filter(Reservation.id == reservation_id)
            .first()
        )

    def update_status(self, reservation: Reservation, status: str) -> Reservation:
        reservation.status = status
        self.db.commit()
        self.db.refresh(reservation)
        return reservation

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

    def get_occupied_capacity_between(
        self,
        environment_id: UUID,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> int:
        reservations = self.db.query(Reservation).filter(
            Reservation.environment_id == environment_id,
            Reservation.status != "cancelled",
        ).all()

        occupied = 0

        for reservation in reservations:
            existing_start = datetime.combine(
                reservation.reservation_date,
                reservation.reservation_time,
            )
            existing_end = existing_start + timedelta(hours=RESERVATION_DURATION_HOURS)

            if existing_start < end_datetime and existing_end > start_datetime:
                occupied += reservation.party_size

        return occupied

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
