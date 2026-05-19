from sqlalchemy.orm import Session

from src.core.security import create_access_token, verify_password
from src.repositories.admin_user_repository import AdminUserRepository
from src.schemas.admin_auth import AdminLoginRequest, AdminLoginResponse, AdminUserResponse


class AdminAuthService:
    def __init__(self, db: Session):
        self.admin_user_repo = AdminUserRepository(db)

    def login(self, login_in: AdminLoginRequest) -> AdminLoginResponse:
        admin_user = self.admin_user_repo.get_by_email(login_in.email)

        if not admin_user or not verify_password(login_in.password, admin_user.password_hash):
            raise ValueError("E-mail ou senha inválidos.")

        if not admin_user.is_active:
            raise ValueError("Usuário inativo.")

        self.admin_user_repo.update_last_login(admin_user)

        return AdminLoginResponse(
            access_token=create_access_token(admin_user.id),
            token_type="bearer",
            user=AdminUserResponse.model_validate(admin_user),
        )