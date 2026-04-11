from datetime import date, time
from uuid import UUID
from pydantic import BaseModel, EmailStr


class ReservationCreate(BaseModel):
    """Schema for public reservation requests."""
    name: str
    email: EmailStr
    phone: str
    environment_id: UUID
    reservation_date: date
    reservation_time: time
    party_size: int
    notes: str | None = None


class ReservationResponse(BaseModel):
    """Minimal schema for reservation response."""
    id: UUID
    status: str
    reservation_date: date
    reservation_time: time