from fastapi import FastAPI

from src.api.endpoints import reservations, environments, availability

app = FastAPI(
    title="Giardini Reservations API",
    description="Backend API for managing reservations, environments, and time availability.",
    version="0.1.0",
)

app.include_router(reservations.router)
app.include_router(environments.router)
app.include_router(availability.router)
