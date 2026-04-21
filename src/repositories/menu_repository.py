from sqlalchemy.orm import Session
from sqlalchemy import text


class MenuRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_menu(self) -> list[dict]:
        query = text("SELECT * FROM public.menu_public_view")
        result = self.db.execute(query).mappings().all()
        return [dict(row) for row in result]
