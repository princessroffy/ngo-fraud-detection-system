from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from app.config import get_settings
from app.models import UserRole
from app.schemas import CurrentUser


def normalize_role(value: str | None) -> UserRole:
    normalized = (value or "").strip().lower()
    role_map = {
        "admin": UserRole.ADMIN,
        "reviewer": UserRole.REVIEWER,
        "viewer": UserRole.VIEWER,
    }
    return role_map.get(normalized, UserRole.VIEWER)


def get_current_user(
    authorization: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
    x_dev_role: str | None = Header(default=None),
) -> CurrentUser:
    settings = get_settings()

    if settings.auth_mode.lower() == "dev":
        email = x_dev_user or "dev-admin@example.org"
        return CurrentUser(id=email, email=email, role=normalize_role(x_dev_role or "Admin"))

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    if not settings.jwt_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing Supabase JWT secret")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_metadata = payload.get("user_metadata") or {}
    app_metadata = payload.get("app_metadata") or {}
    role_value = user_metadata.get("role") or app_metadata.get("role") or payload.get("user_role")

    return CurrentUser(
        id=str(payload.get("sub") or ""),
        email=str(payload.get("email") or ""),
        role=normalize_role(role_value),
    )


def require_roles(*allowed_roles: UserRole) -> Callable[[CurrentUser], CurrentUser]:
    allowed = set(allowed_roles)

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return checker
