"""Amazon S3 service: private bucket upload + short-lived signed GET URLs."""
from __future__ import annotations

import io
from typing import Optional

import boto3
from botocore.client import Config as BotoConfig

from ..config import settings

_client = None


def _endpoint_url() -> Optional[str]:
    """Regional S3 endpoint to sign against.

    Without an explicit endpoint, botocore signs presigned URLs against the
    global host (bucket.s3.amazonaws.com) even when the client resolves a
    regional one. For a bucket outside us-east-1 S3 then answers the signed
    GET with 307 TemporaryRedirect, and an <audio> element just fails to load
    — the redirect target is a different host, so the SigV4 signature no
    longer matches. Signing against the regional host keeps the URL valid.

    S3_ENDPOINT_URL overrides this for MinIO / LocalStack.
    """
    if settings.s3_endpoint_url:
        return settings.s3_endpoint_url
    if settings.aws_region:
        return f"https://s3.{settings.aws_region}.amazonaws.com"
    return None


def client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=_endpoint_url(),
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
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



def delete_key(key: str) -> None:
    """Delete an object. Used to honour erasure requests."""
    client().delete_object(Bucket=settings.s3_bucket, Key=key)
