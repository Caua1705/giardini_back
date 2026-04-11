from datetime import date, time
from uuid import UUID

from sqlalchemy.orm import Session

from src.models import Reservation
from src.repositories import ClientRepository, EnvironmentRepository, ReservationRepository
from src.schemas.reservation import ReservationCreate


class ReservationService:
    def __init__(self, db: Session):
        self.db = db
        self.client_repo = ClientRepository(db)
        self.environment_repo = EnvironmentRepository(db)
        self.reservation_repo = ReservationRepository(db)

    def create_reservation(self, reservation_in: ReservationCreate) -> Reservation:
        environment = self._get_valid_environment(reservation_in.environment_id)

        self._validate_date(reservation_in.reservation_date)
        self._validate_time(
            reservation_in.reservation_date,
            reservation_in.reservation_time,
        )
        self._validate_capacity(
            environment_id=environment.id,
            reservation_date=reservation_in.reservation_date,
            reservation_time=reservation_in.reservation_time,
            party_size=reservation_in.party_size,
            max_capacity=environment.max_capacity,
        )

        client = self._get_or_create_client(
            name=reservation_in.name,
            email=reservation_in.email,
            phone=reservation_in.phone,
        )

        reservation_data = {
            "client_id": client.id,
            "environment_id": environment.id,
            "reservation_date": reservation_in.reservation_date,
            "reservation_time": reservation_in.reservation_time,
            "party_size": reservation_in.party_size,
            "notes": reservation_in.notes,
            "status": "confirmed",
        }

        return self.reservation_repo.create(reservation_data)

    def _get_valid_environment(self, environment_id: UUID):
        environment = self.environment_repo.get_by_id(environment_id)

        if not environment:
            raise ValueError("Ambiente não encontrado.")

        if not environment.is_active:
            raise ValueError("Este ambiente não está disponível para reservas.")

        return environment

    def _get_or_create_client(self, name: str, email: str, phone: str):
        client = self.client_repo.get_by_email(email)

        if client:
            return client

        client_data = {
            "name": name,
            "email": email,
            "phone": phone,
        }

        return self.client_repo.create(client_data)

    def _validate_date(self, reservation_date: date) -> None:
        if reservation_date < date.today():
            raise ValueError("A data da reserva não pode ser no passado.")

        if reservation_date.weekday() == 0:
            raise ValueError("O restaurante está fechado às segundas-feiras.")

    def _validate_time(self, reservation_date: date, reservation_time: time) -> None:
        if reservation_time.minute not in (0, 30) or reservation_time.second != 0:
            raise ValueError("Horários devem ser de 30 em 30 minutos.")

        weekday = reservation_date.weekday()

        if 1 <= weekday <= 5:
            if not (time(7, 0) <= reservation_time <= time(19, 30)):
                raise ValueError("Horário fora do funcionamento.")

        elif weekday == 6:
            if time(7, 0) <= reservation_time <= time(10, 30):
                return

            if time(15, 0) <= reservation_time <= time(18, 30):
                return

            raise ValueError("Horário fora do funcionamento.")

        else:
            raise ValueError("Restaurante fechado neste dia.")

    def _validate_capacity(
        self,
        environment_id: UUID,
        reservation_date: date,
        reservation_time: time,
        party_size: int,
        max_capacity: int,
    ) -> None:
        if party_size > max_capacity:
            raise ValueError(
                f"A quantidade de pessoas excede a capacidade máxima deste ambiente ({max_capacity})."
            )

        occupied = self.reservation_repo.get_occupied_capacity(
            environment_id=environment_id,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
        )

        if occupied + party_size > max_capacity:
            raise ValueError("Não há capacidade disponível para este horário.")