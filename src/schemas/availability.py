from pydantic import BaseModel


class AvailabilityResponse(BaseModel):
    """Schema for a single available time slot."""
    time: str
