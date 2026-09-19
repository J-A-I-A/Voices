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
    given_name/family_name/email. date_of_birth is ALWAYS collected on the
    portal's completion step and sent here (Google does not provide it).
    """
    id_token: str = Field(..., min_length=10)
    date_of_birth: _dt.date
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
    is_reviewer: bool = False
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

