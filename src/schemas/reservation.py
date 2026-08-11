from datetime import date, time
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class ReservationCreate(BaseModel):
    """Schema for public reservation requests."""
    name: str
    email: EmailStr
    phone: str
    environment_id: UUID
    reservation_date: date
    reservation_time: time
    party_size: int = Field(gt=0)
    notes: str | None = None


class ReservationResponse(BaseModel):
    """Schema returned after reservation creation."""
    id: UUID
    status: str
    name: str
    phone: str
    environment_id: UUID
    environment_name: str
    reservation_date: date
    reservation_time: time
    party_size: int