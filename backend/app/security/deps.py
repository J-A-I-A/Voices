"""FastAPI dependencies: current user, reviewer and admin guards."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import User
from .token import decode_access_token
import jose

bearer_scheme = HTTPBearer(auto_error=True)


def _lookup_user(db: Session, user_id: str) -> Optional[User]:
    return db.get(User, user_id)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(creds.credentials)
    except jose.JWTError:
        raise cred_exc
    if payload.get("type") != "access":
        raise cred_exc
    user = _lookup_user(db, payload["sub"])
    if not user:
        raise cred_exc
    # A deleted profile keeps its row (for the consent register) but must not
    # be usable — any token issued before deletion stops working here.
    if user.deleted_at is not None:
        raise cred_exc
    return user


def get_verified_user(user: User = Depends(get_current_user)) -> User:
    """User must be authenticated AND have a verified WhatsApp number."""
    if not user.whatsapp_verified or not user.whatsapp_number:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your WhatsApp number before continuing.",
        )
    return user


def get_reviewer(user: User = Depends(get_current_user)) -> User:
    # Admins can do anything a reviewer can.
    if not (user.is_reviewer or user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer access required.",
        )
    return user


def get_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user

