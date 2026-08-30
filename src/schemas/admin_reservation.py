from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


# Espelha giardini_site.reservation_status. Os rotulos vivem aqui e o service
# deriva a lista deles com get_args: dois lugares para a mesma verdade era como
# a lista do schema e a do service podiam divergir sem ninguem perceber.
ReservationStatus = Literal[
    "confirmed",
    "reminded",
    "reconfirmed",
    "cancelled",
    "completed",
    "no_show",
]


class AdminReservationStatusUpdateRequest(BaseModel):
    status: ReservationStatus


class AdminReservationItemResponse(BaseModel):
    id: UUID

    reservation_date: date
    reservation_time: time
    party_size: int
    status: str
    notes: str | None
    created_at: datetime

    client_id: UUID
    client_name: str
    client_email: EmailStr
    client_phone: str

    environment_id: UUID
    environment_name: str
    environment_max_capacity: int


class AdminReservationSummaryResponse(BaseModel):
    total_reservations: int
    today_reservations: int
    total_guests: int
    upcoming_reservations: int


class AdminReservationListResponse(BaseModel):
    summary: AdminReservationSummaryResponse
    items: list[AdminReservationItemResponse]
