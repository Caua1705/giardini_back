from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies.admin_auth import get_current_admin_user
from src.db.session import get_db
from src.models.admin_user_model import AdminUser
from src.schemas.admin_auth import AdminLoginRequest, AdminLoginResponse, AdminUserResponse
from src.services.admin_auth_service import AdminAuthService

router = APIRouter(prefix="/admin", tags=["Admin Auth"])


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    summary="Admin login",
    description="Authenticates an admin user and returns a JWT access token.",
)
def admin_login(
    login_in: AdminLoginRequest,
    db: Session = Depends(get_db),
):
    service = AdminAuthService(db)
    try:
        return service.login(login_in)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get(
    "/me",
    response_model=AdminUserResponse,
    summary="Get current admin user",
    description="Returns the authenticated admin user data.",
)
def admin_me(
    current_admin: AdminUser = Depends(get_current_admin_user),
):
    return current_admin
