"""Authentication router: register (email / Google), login, Google completion, WhatsApp OTP."""
from __future__ import annotations

import datetime as _dt
import logging

import jose
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.user import User, AuthProvider
from ..schemas.auth import (
    RegisterEmailRequest, GoogleAuthRequest,
    LoginRequest, TokenResponse, UserOut, VerifyWhatsappRequest,
    CheckOtpRequest, ResendOtpRequest, MeResponse, GoogleAuthResult,
    VerifyEmailRequest,
)
from ..security.age import is_at_least_18
from ..security.deps import get_current_user, get_verified_user
from ..security.hashing import hash_password, verify_password
from ..security.token import create_access_token, create_email_verify_token, decode_email_verify_token
from ..services.email import send_verification_email, EmailError
from ..services.google import verify_id_token, GoogleTokenError, claims_to_names
from ..services.otp import issue_otp, verify_code, OTPError, CooldownActive
from ..services.rate_limit import hit_rate_limit
from ..services.whatsapp import send_otp, agent_wame_link, WhatsAppError

logger = logging.getLogger("carib.auth")
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
        email_verified=user.email_verified,
        is_reviewer=user.is_reviewer,
        is_admin=user.is_admin,
        requires_completion=not bool(user.date_of_birth),
    )


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_to_out(user),
        requires_completion=not bool(user.date_of_birth),
    )


def _sync_configured_roles(user: User, db: Session | None = None) -> None:
    """Apply REVIEWER_EMAILS / ADMIN_EMAILS to this account.

    Called on login as well as registration: the original code only ran at
    registration, so adding an address to the list had no effect on an account
    that already existed — the flag could only be set with a manual UPDATE.
    Roles granted in the admin UI are never revoked here; the lists only add.
    """
    changed = False
    if user.email.lower() in settings.reviewer_email_list and not user.is_reviewer:
        user.is_reviewer = True
        changed = True
    if user.email.lower() in settings.admin_email_list and not user.is_admin:
        user.is_admin = True
        changed = True
    if changed and db is not None:
        db.commit()
        logger.info("roles synced from config for %s (reviewer=%s admin=%s)",
                    user.email, user.is_reviewer, user.is_admin)


# Back-compat alias for existing call sites.
_mark_reviewer_if_configured = _sync_configured_roles


# ─── Email registration ─────────────────────────────────────
@router.post("/register/email", response_model=TokenResponse)
async def register_email(
    body: RegisterEmailRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
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
        email_verified=False,
    )
    _mark_reviewer_if_configured(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    # Sent after the response so a slow or failing mail provider never blocks
    # sign-up; the dashboard offers a resend.
    background.add_task(_send_verification_logged, user.id, user.email, user.first_name)
    return _token_for(user)


# ─── Email verification ────────────────────────────────────
def _verification_link(user_id: str, email: str) -> str:
    token = create_email_verify_token(user_id, email)
    return f"{settings.portal_base_url.rstrip('/')}/verify-email?token={token}"


async def _send_verification_logged(user_id: str, email: str, first_name: str) -> None:
    try:
        await send_verification_email(email, first_name, _verification_link(user_id, email))
    except EmailError as e:
        logger.error("verification email to %s failed: %s", email, e)


@router.post("/email/verify", response_model=MeResponse)
async def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Confirm an email address from the mailed link.

    Unauthenticated on purpose: the link is often opened in a different
    browser (or the phone's mail app) from the one the user signed up in.
    """
    invalid = HTTPException(
        status_code=400,
        detail="This confirmation link is invalid or has expired. Sign in and request a new one.",
    )
    try:
        payload = decode_email_verify_token(body.token)
    except jose.JWTError:
        raise invalid
    user = db.get(User, payload.get("sub"))
    if not user or user.deleted_at is not None or user.email != payload.get("email"):
        raise invalid
    if not user.email_verified:
        user.email_verified = True
        db.commit()
        db.refresh(user)
    return _user_to_out(user)


@router.post("/email/resend")
async def resend_verification_email(request: Request, user: User = Depends(get_current_user)):
    if user.email_verified:
        return {"status": "already_verified"}
    if hit_rate_limit(f"email_verify:{user.id}", 1, settings.email_resend_cooldown_seconds):
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {settings.email_resend_cooldown_seconds}s before requesting another email.",
        )
    if hit_rate_limit(f"email_verify_hr:{user.id}", 5, 3600):
        raise HTTPException(status_code=429, detail="Too many emails requested. Try again later.")
    try:
        await send_verification_email(user.email, user.first_name, _verification_link(user.id, user.email))
    except EmailError as e:
        logger.error("verification email to %s failed: %s", user.email, e)
        raise HTTPException(status_code=502, detail="We could not send the email. Please try again shortly.") from e
    return {"status": "sent", "email": user.email}


# ─── Google sign-in / sign-up ──────────────────────────────
def _google_result(user: User) -> GoogleAuthResult:
    return GoogleAuthResult(
        requires_completion=False,
        access_token=create_access_token(user.id),
        user=_user_to_out(user),
    )


@router.post("/google", response_model=GoogleAuthResult)
async def google_auth(body: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)):
    """Google sign-in and sign-up.

    Google does not supply a date of birth, so the portal collects one on a
    completion step. That step is only needed when we do not already hold the
    details: a returning user signs straight in. Previously the portal routed
    every Google sign-in through the completion form and the request schema
    required a DOB, so returning users were asked for their name and date of
    birth on every single sign-in.
    """
    if hit_rate_limit(f"register:{request.client.host}", 10, 600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    try:
        claims = await verify_id_token(body.id_token)
    except GoogleTokenError as e:
        raise HTTPException(status_code=400, detail=f"Google sign-in failed: {e}") from e

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google token did not include an email.")
    google_sub = claims.get("sub")
    # Google reports this as a bool (occasionally the string "true").
    google_email_verified = str(claims.get("email_verified", "")).lower() == "true"
    given, family = claims_to_names(claims)

    # The age gate is enforced server-side whenever a DOB is supplied.
    if body.date_of_birth is not None and not is_at_least_18(body.date_of_birth):
        raise _age_rejected()

    user = db.query(User).filter(User.email == email).first()
    if user is not None and user.deleted_at is not None:
        # Deleted rows are scrubbed to a placeholder email, so this is a guard
        # rather than a path users can normally reach.
        user = None

    if user:
        if user.auth_provider != AuthProvider.google:
            raise HTTPException(
                status_code=409,
                detail="This email is registered with a password. Please sign in with email + password.",
            )

        # Returning user with everything on file: sign in, change nothing.
        if body.date_of_birth is None:
            if user.date_of_birth:
                user.google_subject = google_sub
                user.email_verified = user.email_verified or google_email_verified
                _sync_configured_roles(user)
                db.commit()
                db.refresh(user)
                return _google_result(user)
            # Account exists but has no DOB — ask for it, prefilling what we know.
            return GoogleAuthResult(
                requires_completion=True,
                first_name=user.first_name or given,
                last_name=user.last_name or family,
                email=email,
            )

        # Completion step (or a deliberate update) supplied details.
        user.google_subject = google_sub
        user.email_verified = user.email_verified or google_email_verified
        if body.first_name:
            user.first_name = body.first_name.strip()
        elif given and not user.first_name:
            user.first_name = given
        if body.last_name:
            user.last_name = body.last_name.strip()
        elif family and not user.last_name:
            user.last_name = family
        user.date_of_birth = body.date_of_birth
        _sync_configured_roles(user)
        db.commit()
        db.refresh(user)
        return _google_result(user)

    # New account: we must collect a DOB before creating anything, both for the
    # 18+ gate and because the column is non-nullable.
    if body.date_of_birth is None:
        return GoogleAuthResult(
            requires_completion=True,
            first_name=given,
            last_name=family,
            email=email,
        )

    user = User(
        first_name=(body.first_name or given or "").strip() or "User",
        last_name=(body.last_name or family or "").strip(),
        date_of_birth=body.date_of_birth,
        email=email,
        auth_provider=AuthProvider.google,
        google_subject=google_sub,
        password_hash=None,
        email_verified=google_email_verified,
    )
    _sync_configured_roles(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _google_result(user)


# ─── Email login ────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if hit_rate_limit(f"login:{request.client.host}", 15, 600):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or user.deleted_at is not None or user.auth_provider != AuthProvider.email:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(body.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _sync_configured_roles(user, db)
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
    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Please confirm your email address first — check your inbox for the link.",
        )
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

    try:
        await send_otp(phone.lstrip("+"), code)
    except WhatsAppError as e:
        # The code is already issued, so surface a real reason rather than a
        # bare 500 — the Graph details are in the log line.
        logger.error("OTP delivery to %s failed: %s", phone, e)
        raise HTTPException(
            status_code=502,
            detail="We could not send the verification code over WhatsApp. Please try again shortly.",
        ) from e
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
