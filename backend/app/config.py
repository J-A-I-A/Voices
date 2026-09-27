"""Application configuration, all env-driven via pydantic-settings."""
from __future__ import annotations

import logging

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
    # Comma-separated emails granted admin. Unlike reviewer_emails (which the
    # original code applied only at registration), these are re-applied on
    # every login, so adding an address promotes an existing account.
    admin_emails: str = ""
    # Version of the Privacy Notice contributors consent to. Bump this when
    # the notice changes materially so prior consent is not assumed to cover it.
    privacy_policy_version: str = "2026-10-01"

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
    # Approved authentication template used to deliver verification codes.
    # A user verifying their number normally has no 24-hour customer service
    # window open, so a free-form text would be rejected with code 131047.
    whatsapp_otp_template: str = "number_verification"
    # Reference only — /messages sends by name+language. The id addresses
    # the template-management API, e.g.
    #   GET https://graph.facebook.com/v20.0/<id>?fields=name,language,status,category,components
    whatsapp_otp_template_id: str = "26362065543403544"
    # Exact language code of the approved template — Meta treats "en" and
    # "en_US" as different templates, so a mismatch fails with code 132001.
    whatsapp_otp_template_lang: str = "en"
    whatsapp_use_otp_template: bool = True
    # Inbound messages older than this are treated as retries of past
    # traffic. Audio is still stored; anything else is ignored rather
    # than answered with a phrase the contributor never asked for.
    whatsapp_stale_message_seconds: int = 900
    # The approved template is in Meta's authentication category: body
    # parameter + security disclaimer + expiry footer + copy-code button.
    # The button must be sent the same code or Graph rejects the send.
    whatsapp_otp_template_copy_code: bool = True

    # AWS / S3
    s3_bucket: str = "carib-voices-voicenotes"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_signed_url_expiry_seconds: int = 300
    # Override the S3 endpoint (MinIO / LocalStack). Empty means the
    # regional AWS endpoint, which presigned URLs must be signed against.
    s3_endpoint_url: str = ""

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

    # Phrase length bands. Word thresholds are derived from these seconds and
    # the speaking rate, so tuning the rate moves every band together.
    phrase_words_per_minute: int = 150
    phrase_short_max_seconds: int = 10
    phrase_medium_max_seconds: int = 20
    phrase_long_max_seconds: int = 35

    # OTP
    # Must match the approved template's expiry footer
    # ("Expires in 15 minutes"), or the message promises longer
    # than the code actually lives.
    otp_ttl_seconds: int = 900
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60

    @field_validator("agent_whatsapp_number")
    @classmethod
    def _strip_plus(cls, v: str) -> str:
        return v.lstrip("+").strip()

    @field_validator("whatsapp_phone_number_id")
    @classmethod
    def _check_phone_number_id(cls, v: str) -> str:
        """Warn loudly on a malformed phone number id.

        Graph builds the send URL from this value, so a stray character turns
        every outbound message into an opaque 400. We only strip surrounding
        whitespace — silently rewriting the value could mask a genuinely wrong
        id — and log the rest.
        """
        v = v.strip()
        if v and not v.isdigit():
            logging.getLogger("carib.config").error(
                "WHATSAPP_PHONE_NUMBER_ID=%r is not all digits. Every WhatsApp "
                "send will fail with HTTP 400 until this is corrected.",
                v,
            )
        return v

    @property
    def reviewer_email_list(self) -> List[str]:
        return [e.strip().lower() for e in self.reviewer_emails.split(",") if e.strip()]

    @property
    def admin_email_list(self) -> List[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

