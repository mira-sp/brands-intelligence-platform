# backend/app/core/security.py
"""Authentication & authorization.

Two ways to authenticate:
  * ``Authorization: Bearer <JWT>`` - issued by ``POST /auth/token`` for user accounts
  * ``X-API-Key: <key>``            - service-to-service, grants the "admin" role

Use ``Depends(require_role("admin", "analyst"))`` or ``Depends(require_user)`` on endpoints.
"""
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Used to keep login timing constant when the user does not exist
_DUMMY_HASH = pwd_context.hash(secrets.token_urlsafe(16))

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


@dataclass
class Principal:
    id: str
    email: str
    role: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: Optional[str]) -> bool:
    if not hashed:
        pwd_context.verify(password, _DUMMY_HASH)
        return False
    return pwd_context.verify(password, hashed)


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def require_user(
    token: Optional[str] = Depends(_oauth2_scheme),
    api_key: Optional[str] = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if settings.auth_bypass:
        return Principal(id="dev", email="dev@localhost", role="admin")

    if api_key:
        if settings.api_key and secrets.compare_digest(api_key.encode(), settings.api_key.encode()):
            return Principal(id="service", email="service", role="admin")
        raise _UNAUTHORIZED

    if not token:
        raise _UNAUTHORIZED
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise _UNAUTHORIZED
    if payload.get("type") != "access" or not payload.get("sub"):
        raise _UNAUTHORIZED

    # Re-check the account on every request so deactivation / role changes apply immediately
    from ..models.user import User
    user = (await db.execute(select(User).where(User.id == payload["sub"]))).scalar_one_or_none()
    if not user or not user.is_active:
        raise _UNAUTHORIZED
    return Principal(id=user.id, email=user.email, role=user.role)


def require_role(*roles: str):
    async def _check(principal: Principal = Depends(require_user)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return principal
    return _check


# Backwards-compatible name used by existing routers
require_api_key = require_user
