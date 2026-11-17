# backend/app/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from ..core.database import Base
import uuid

ROLES = ("admin", "analyst", "viewer")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    # admin: manage users + everything; analyst: write data + run ML; viewer: run ML (read-only data)
    role = Column(String, nullable=False, default="viewer")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
