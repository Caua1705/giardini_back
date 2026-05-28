from hmac import compare_digest
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core import config as settings
from src.core.security import decode_access_token
from src.db.session import get_db
from src.models.admin_user_model import AdminUser
from src.repositories.admin_user_repository import AdminUserRepository


bearer_scheme = HTTPBearer()


def _get_active_admin_user_from_token(token: str, db: Session) -> AdminUser | None:
    try:
        payload = decode_access_token(token)
        admin_user_id = UUID(payload["sub"])
    except Exception:
        return None

    admin_user = AdminUserRepository(db).get_by_id(admin_user_id)

    if not admin_user or not admin_user.is_active:
        return None

    return admin_user


def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    admin_user = _get_active_admin_user_from_token(credentials.credentials, db)

    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    return admin_user


def validate_admin_or_internal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminUser | None:
    if x_api_key and compare_digest(x_api_key, settings.INTERNAL_API_KEY):
        return None

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            admin_user = _get_active_admin_user_from_token(token, db)
            if admin_user:
                return admin_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials or internal API key",
    )
