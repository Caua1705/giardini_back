from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.admin_user_model import AdminUser


class AdminUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> AdminUser | None:
        return (
            self.db.query(AdminUser)
            .filter(func.lower(AdminUser.email) == email.lower())
            .first()
        )

    def get_by_id(self, admin_user_id: UUID) -> AdminUser | None:
        return (
            self.db.query(AdminUser)
            .filter(AdminUser.id == admin_user_id)
            .first()
        )

    def update_last_login(self, admin_user: AdminUser) -> None:
        admin_user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(admin_user)
