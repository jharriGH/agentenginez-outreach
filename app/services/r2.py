import boto3
from botocore.client import Config

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _client():
    if not settings.R2_ACCOUNT_ID:
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    c = _client()
    if c is None:
        log.warning("r2_skipped_no_creds", key=key)
        return f"local://{key}"
    c.put_object(Bucket=settings.R2_BUCKET, Key=key, Body=data, ContentType=content_type)
    base = settings.R2_PUBLIC_BASE.rstrip("/") if settings.R2_PUBLIC_BASE else ""
    return f"{base}/{key}" if base else f"r2://{settings.R2_BUCKET}/{key}"
