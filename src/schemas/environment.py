from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class EnvironmentResponse(BaseModel):
    """Schema for environment listings in the public API."""
    id: UUID
    name: str
    max_capacity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime