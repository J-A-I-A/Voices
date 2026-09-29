"""Auth request/response schemas."""
from __future__ import annotations

import datetime as _dt
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from ..security.phone import normalize_jamaican, InvalidJamaicanNumberError


class RegisterEmailRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    date_of_birth: _dt.date
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    """Submitted by the portal after Google sign-in returns an ID token.

    The portal sends Google's id_token; the backend verifies it and reads
    given_name/family_name/email. Google never provides a date of birth, so
    it is collected on the portal's completion step — but only the FIRST
    time. `date_of_birth` is therefore optional: a returning user who already
    has one on file signs straight in, and the backend answers
    requires_completion when it genuinely still needs the details.
    """
    id_token: str = Field(..., min_length=10)
    date_of_birth: Optional[_dt.date] = None
    first_name: Optional[str] = Field(None, max_length=120)
    last_name: Optional[str] = Field(None, max_length=120)


class CompleteGoogleRequest(BaseModel):
    """Complete a Google account that already exists but needs finalization."""
    date_of_birth: _dt.date
    first_name: Optional[str] = Field(None, max_length=120)
    last_name: Optional[str] = Field(None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: "UserOut"
    requires_completion: bool = False


class GoogleAuthResult(BaseModel):
    """Either a completed sign-in, or a request for the missing details.

    Kept field-compatible with TokenResponse on the success path so callers
    can use it the same way; access_token/user are null only when
    requires_completion is true.
    """
    requires_completion: bool = False
    access_token: Optional[str] = None
    token_type: Literal["bearer"] = "bearer"
    user: Optional["UserOut"] = None
    # Prefill for the completion step, from the Google profile.
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    first_name: str
    last_name: str
    date_of_birth: _dt.date
    email: str
    auth_provider: str
    whatsapp_number: Optional[str] = None
    whatsapp_verified: bool = False
    email_verified: bool = False
    is_reviewer: bool = False
    is_admin: bool = False
    requires_completion: bool = False  # True for Google users needing DOB completion

    @property
    def age(self) -> int:
        from ..security.age import age_from_dob
        return age_from_dob(self.date_of_birth)


TokenResponse.model_rebuild()


class VerifyWhatsappRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        try:
            return normalize_jamaican(v)
        except InvalidJamaicanNumberError as e:
            raise ValueError(str(e)) from e


class CheckOtpRequest(BaseModel):
    phone: str
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        try:
            return normalize_jamaican(v)
        except InvalidJamaicanNumberError as e:
            raise ValueError(str(e)) from e


class ResendOtpRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        try:
            return normalize_jamaican(v)
        except InvalidJamaicanNumberError as e:
            raise ValueError(str(e)) from e


class MeResponse(UserOut):
    pass


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2048)

