from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.endpoints import reservations, environments, availability

app = FastAPI(
    title="Giardini Reservations API",
    description="Backend API for managing reservations, environments, and time availability.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reservations.router)
app.include_router(environments.router)
app.include_router(availability.router)