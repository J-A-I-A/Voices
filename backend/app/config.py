"""Application configuration, all env-driven via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # App
    debug: bool = False
    portal_base_url: str = "http://localhost:3000"
    backend_port: int = 8000
    reviewer_emails: str = ""

    # Database / cache
    database_url: str = "postgresql+psycopg://carib:caribvoices@localhost:5432/caribvoices"
    redis_url: str = "redis://localhost:6379/0"

    # Auth / JWT
    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    access_token_ttl_minutes: int = 60
    google_client_id: str = ""
    google_client_secret: str = ""

    # WhatsApp (Meta Cloud API)
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    agent_whatsapp_number: str = ""  # digits-only, no '+'

    # AWS / S3
    s3_bucket: str = "carib-voices-voicenotes"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_signed_url_expiry_seconds: int = 300

    # ASR / QC
    runpod_asr_endpoint: str = ""
    runpod_api_key: str = ""
    fallback_asr_model: str = "small"
    wer_accept_max: float = 0.30
    wer_reject_min: float = 0.60
    min_duration_s: float = 1.0
    max_duration_s: float = 60.0
    min_vad_ratio: float = 0.25
    min_snr_db: float = 8.0
    min_loudness_dbfs: float = -40.0
    max_loudness_dbfs: float = -3.0
    max_clipping_ratio: float = 0.05

    # OTP
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60

    @field_validator("agent_whatsapp_number")
    @classmethod
    def _strip_plus(cls, v: str) -> str:
        return v.lstrip("+").strip()

    @property
    def reviewer_email_list(self) -> List[str]:
        return [e.strip().lower() for e in self.reviewer_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

