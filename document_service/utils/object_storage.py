"""Object storage utilities for R2."""

import os
import logging
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from document_service.config import get_settings

logger = logging.getLogger("document-service.object-storage")
settings = get_settings()

ACCOUNT_ID = settings.r2_account_id
ACCESS_KEY = settings.r2_access_key_id
SECRET_KEY = settings.r2_secret_access_key
BUCKET_NAME = settings.r2_bucket_name

ENDPOINT = settings.r2_endpoint or f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
REGION = "auto"
PRESIGN_EXPIRY_SECONDS = 3600


if not ACCOUNT_ID:
    logger.warning("R2_ACCOUNT_ID not configured")

if not ACCESS_KEY or not SECRET_KEY:
    logger.warning("R2 credentials not configured")

if not BUCKET_NAME:
    logger.warning("R2 bucket name not configured")

s3_client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION,
    config=Config(signature_version="s3v4"),
)


def get_storage_folder(status: str) -> str:
    """Map document version status to storage folder."""
    mapping = {
        "pending": "pending",               # Temporary uploads in progress
        "uploaded": "unprocessed",          # Upload complete, awaiting security scan
        "security_pending": "unprocessed",  # Queued for security checks
        "security_running": "unprocessed",  # Security checks in progress
        "security_failed": "quarantined",   # Security failed
        "processing_failed": "quarantined", # Processing failed
        "ingesting": "unprocessed",
        "available": "safe",                # Security passed, ready for use
        "quarantined": "quarantined",       # Security failed (legacy)
        "aborted": "unprocessed",
    }
    return mapping.get(status, "unprocessed")


def build_object_key(org_id: str, document_id: str, version_id: str, status: str) -> str:
    """Build object key with status-based folder prefix."""
    folder = get_storage_folder(status)
    return f"{folder}/{org_id}/{document_id}/{version_id}"


def move_object(source_key: str, destination_key: str) -> None:
    """Move an object from source_key to destination_key via copy + delete.
    R2 doesn't have a native move, so we copy then delete source."""
    try:
        copy_source = {"Bucket": BUCKET_NAME, "Key": source_key}
        s3_client.copy(copy_source, BUCKET_NAME, destination_key)
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=source_key)
        logger.info(
            "Object moved",
            extra={"extra_data": {"sourceKey": source_key, "destinationKey": destination_key}},
        )
    except ClientError:
        logger.error(
            "Failed to move object",
            extra={"extra_data": {"sourceKey": source_key, "destinationKey": destination_key}},
            exc_info=True,
        )
        raise


def download_url(object_key: str, filename: str) -> str:
    """Generate presigned URL for downloading an object."""
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": object_key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=PRESIGN_EXPIRY_SECONDS,
    )


def get_object(object_key: str, local_path: str) -> bool:
    """Download object directly to local path."""
    try:
        s3_client.download_file(BUCKET_NAME, object_key, local_path)
        logger.info(f"Downloaded {object_key} to {local_path}")
        return True
    except ClientError as e:
        logger.error(f"Failed to download {object_key}: {e}")
        return False


def head_object(object_key: str) -> dict | None:
    """Get object metadata."""
    try:
        return s3_client.head_object(Bucket=BUCKET_NAME, Key=object_key)
    except ClientError:
        return None


def delete_object(object_key: str) -> bool:
    """Delete object from R2."""
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=object_key)
        logger.info(f"Deleted object {object_key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete {object_key}: {e}")
        return False