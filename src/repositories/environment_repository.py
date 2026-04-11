from sqlalchemy.orm import Session
from src.models import Environment
from uuid import UUID


class EnvironmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_active(self) -> list[Environment]:
        return self.db.query(Environment).filter(Environment.is_active == True).all()

    def get_by_id(self, environment_id: UUID) -> Environment | None:
        return self.db.query(Environment).filter(Environment.id == environment_id).first()
