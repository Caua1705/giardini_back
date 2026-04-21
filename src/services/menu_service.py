from sqlalchemy.orm import Session

from src.repositories.menu_repository import MenuRepository


class MenuService:
    def __init__(self, db: Session):
        self.db = db
        self.menu_repo = MenuRepository(db)

    def get_menu(self) -> list[dict]:
        return self.menu_repo.get_menu()
