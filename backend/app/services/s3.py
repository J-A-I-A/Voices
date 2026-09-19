"""Amazon S3 service: private bucket upload + short-lived signed GET URLs."""
from __future__ import annotations

import io
from typing import Optional

import boto3
from botocore.client import Config as BotoConfig

from ..config import settings

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            config=BotoConfig(signature_version="s3v4"),
        )
    return _client


def upload_bytes(key: str, data: bytes, mime_type: Optional[str] = None) -> str:
    """Upload bytes to the private bucket and return the key."""
    client().upload_fileobj(
        io.BytesIO(data),
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": mime_type or "application/octet-stream"},
    )
    return key


def presigned_get_url(key: str, expires: Optional[int] = None) -> str:
    return client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires or settings.s3_signed_url_expiry_seconds,
    )

