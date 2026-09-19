"""Authentication router: register (email / Google), login, Google completion, WhatsApp OTP."""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.user import User, AuthProvider
from ..schemas.auth import (
    RegisterEmailRequest, GoogleAuthRequest,
    LoginRequest, TokenResponse, UserOut, VerifyWhatsappRequest,
    CheckOtpRequest, ResendOtpRequest, MeResponse,
)
from ..security.age import is_at_least_18
from ..security.deps import get_current_user, get_verified_user
from ..security.hashing import hash_password, verify_password
from ..security.token import create_access_token
from ..services.google import verify_id_token, GoogleTokenError, claims_to_names
from ..services.otp import issue_otp, verify_code, OTPError, CooldownActive
from ..services.rate_limit import hit_rate_limit
from ..services.whatsapp import send_otp, agent_wame_link

router = APIRouter(prefix="/auth", tags=["auth"])

WAME_STARTER = "Hi Carib Voices! Send me a phrase to read."


def _age_rejected() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="You must be 18 or older to register.",
    )


def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        date_of_birth=user.date_of_birth,
        email=user.email,
        auth_provider=user.auth_provider.value,
        whatsapp_number=user.whatsapp_number,
        whatsapp_verified=user.whatsapp_verified,
        is_reviewer=user.is_reviewer,
        requires_completion=not bool(user.date_of_birth),
    )


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_to_out(user),
        requires_completion=not bool(user.date_of_birth),
    )


def _mark_reviewer_if_configured(user: User) -> None:
    if user.email.lower() in settings.reviewer_email_list:
        user.is_reviewer = True


# ─── Email registration ─────────────────────────────────────
@router.post("/register/email", response_model=TokenResponse)
async def register_email(body: RegisterEmailRequest, request: Request, db: Session = Depends(get_db)):
    if hit_rate_limit(f"register:{request.client.host}", 10, 600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    if not is_at_least_18(body.date_of_birth):
        raise _age_rejected()

    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        date_of_birth=body.date_of_birth,
        email=body.email.lower(),
        auth_provider=AuthProvider.email,
        password_hash=hash_password(body.password),
    )
    _mark_reviewer_if_configured(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


# ─── Google sign-in / sign-up ──────────────────────────────
@router.post("/google", response_model=TokenResponse)
async def google_auth(body: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)):
    if hit_rate_limit(f"register:{request.client.host}", 10, 600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    # The portal always collects DOB on the Google completion step, so the
    # request carries it. Validate the age gate server-side regardless.
    if not is_at_least_18(body.date_of_birth):
        raise _age_rejected()

    try:
        claims = await verify_id_token(body.id_token)
    except GoogleTokenError as e:
        raise HTTPException(status_code=400, detail=f"Google sign-in failed: {e}") from e

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google token did not include an email.")
    google_sub = claims.get("sub")

    user = db.query(User).filter(User.email == email).first()
    given, family = claims_to_names(claims)

    if user:
        if user.auth_provider != AuthProvider.google:
            raise HTTPException(
                status_code=409,
                detail="This email is registered with a password. Please sign in with email + password.",
            )
        user.google_subject = google_sub
        # Only persist Google-provided name fields when the claims/form actually provide them.
        if body.first_name:
            user.first_name = body.first_name.strip()
        elif given and not user.first_name:
            user.first_name = given
        if body.last_name:
            user.last_name = body.last_name.strip()
        elif family and not user.last_name:
            user.last_name = family
        user.date_of_birth = body.date_of_birth
        _mark_reviewer_if_configured(user)
        db.commit()
        db.refresh(user)
        return _token_for(user)

    user = User(
        first_name=(body.first_name or given or "").strip() or "User",
        last_name=(body.last_name or family or "").strip(),
        date_of_birth=body.date_of_birth,
        email=email,
        auth_provider=AuthProvider.google,
        google_subject=google_sub,
        password_hash=None,
    )
    _mark_reviewer_if_configured(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


# ─── Email login ────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if hit_rate_limit(f"login:{request.client.host}", 15, 600):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or user.auth_provider != AuthProvider.email:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(body.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _token_for(user)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return _user_to_out(user)


@router.get("/agent-link")
async def agent_link(user: User = Depends(get_verified_user)):
    """wa.me deep link to the agent, with prefilled starter text."""
    return {"agent_url": agent_wame_link(WAME_STARTER)}


# ─── WhatsApp verification: request OTP ────────────────────
@router.post("/verify/request")
async def request_otp(
    body: VerifyWhatsappRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _send_otp(body, request, user, db)


@router.post("/verify/resend")
async def resend_otp(
    body: ResendOtpRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _send_otp(body, request, user, db)


async def _send_otp(body, request, user, db):
    phone = body.phone  # already normalized by Pydantic validator
    if hit_rate_limit(f"otp_req:{phone}", 5, 600):
        raise HTTPException(status_code=429, detail="Too many OTP requests for this number.")
    if hit_rate_limit(f"otp_req:{request.client.host}", 10, 600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    other = db.query(User).filter(User.whatsapp_number == phone, User.id != user.id).first()
    if other and other.whatsapp_verified:
        raise HTTPException(status_code=409, detail="This WhatsApp number is already verified to another account.")

    try:
        code = issue_otp(db, user, phone)
    except CooldownActive as e:
        raise HTTPException(status_code=429, detail=str(e)) from e

    await send_otp(phone.lstrip("+"), code)
    return {"status": "sent", "phone": phone}


# ─── WhatsApp verification: check OTP ──────────────────────
@router.post("/verify/check")
async def check_otp(
    body: CheckOtpRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        vc = verify_code(db, body.phone, body.code)
    except OTPError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not vc:
        raise HTTPException(status_code=400, detail="Incorrect code. Please try again.")

    user.whatsapp_number = body.phone
    user.whatsapp_verified = True
    db.commit()
    return {
        "status": "verified",
        "phone": user.whatsapp_number,
        "agent_url": agent_wame_link(WAME_STARTER),
    }
