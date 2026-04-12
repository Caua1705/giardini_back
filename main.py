from fastapi import FastAPI

from src.api.endpoints import reservations, environments, availability

app = FastAPI()

app.include_router(reservations.router)
app.include_router(environments.router)
app.include_router(availability.router)