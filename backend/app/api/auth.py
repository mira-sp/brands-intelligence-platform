# backend/app/api/auth.py
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import (
    Principal,
    create_access_token,
    hash_password,
    require_role,
    require_user,
    verify_password,
)
from ..models.user import ROLES, User

router = APIRouter(prefix="/auth", tags=["Auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "viewer"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 254 or not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if len(v.encode()) > 72:  # bcrypt truncates beyond 72 bytes
            raise ValueError("Password must be at most 72 bytes")
        return v

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"Role must be one of {ROLES}")
        return v


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    email = form.username.strip().lower()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    # verify_password runs a dummy hash when user is None -> no user-enumeration via timing
    if not verify_password(form.password, user.hashed_password if user else None) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@router.get("/me")
async def me(principal: Principal = Depends(require_user)):
    return {"id": principal.id, "email": principal.email, "role": principal.role}


@router.get("/users", response_model=List[UserOut])
async def list_users(_: Principal = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User))).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    _: Principal = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    exists = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(email=body.email, hashed_password=hash_password(body.password), role=body.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    principal: Principal = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == principal.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user
