from sqlalchemy.orm import Session

from src.repositories.menu_repository import MenuRepository
from src.utils.storage import build_image_url
from src.core import config as settings


class MenuService:
    def __init__(self, db: Session):
        self.db = db
        self.menu_repo = MenuRepository(db)

    def get_menu(self) -> list[dict]:
        menu_items = self.menu_repo.get_menu()

        for item in menu_items:
            item["image_url"] = build_image_url(
                item.get("image_path"),
                settings.SUPABASE_MENU_BUCKET,
            )

        return menu_items