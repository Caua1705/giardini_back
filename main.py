from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.endpoints import reservations, environments, availability, menu

app = FastAPI(
    title="Giardini Reservations API",
    description="Backend API for managing reservations, environments, and time availability.",
    version="0.1.0",
)

origins = [
    "https://giardini.cafe",
    "https://www.giardini.cafe",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reservations.router)
app.include_router(environments.router)
app.include_router(availability.router)
app.include_router(menu.router)