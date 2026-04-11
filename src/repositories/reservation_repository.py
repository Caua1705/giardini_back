from sqlalchemy.orm import Session
from src.models import Reservation


class ReservationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, reservation_data: dict) -> Reservation:
        db_reservation = Reservation(**reservation_data)
        self.db.add(db_reservation)
        self.db.commit()
        self.db.refresh(db_reservation)
        return db_reservation