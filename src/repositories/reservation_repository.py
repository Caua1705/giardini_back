from sqlalchemy import func
from sqlalchemy.orm import Session
from src.models import Reservation
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

    def get_occupied_capacity(self, environment_id: UUID, reservation_date: date, reservation_time: time) -> int:
        """Sums the party_size for all reservations in a specific slot."""
        total = self.db.query(func.sum(Reservation.party_size)).filter(
            Reservation.environment_id == environment_id,
            Reservation.reservation_date == reservation_date,
            Reservation.reservation_time == reservation_time
        ).scalar()
        return total or 0