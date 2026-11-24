"""Object storage utilities for R2."""

import os
import logging
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from config import get_settings

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