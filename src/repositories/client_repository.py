from sqlalchemy.orm import Session
from src.models import Client

class ClientRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Client | None:
        return self.db.query(Client).filter(Client.email == email).first()

    def create(self, client_data: dict) -> Client:
        db_client = Client(**client_data)
        self.db.add(db_client)
        self.db.commit()
        self.db.refresh(db_client)
        return db_client
