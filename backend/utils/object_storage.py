import os
import math
import logging

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("app.utils.object_storage")

ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
CHUNK_SIZE = int(os.getenv("R2_OBJECT_CHUNK_SIZE", "0"))

ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
REGION = "auto"
PRESIGN_EXPIRY_SECONDS = int(os.getenv("R2_PRESIGN_EXPIRY_SECONDS", "3600"))
MAX_PRESIGN_EXPIRY_SECONDS = 604800

if not 1 <= PRESIGN_EXPIRY_SECONDS <= MAX_PRESIGN_EXPIRY_SECONDS:
    raise RuntimeError(f"R2 presign expiry must be between 1 and {MAX_PRESIGN_EXPIRY_SECONDS} seconds")

if not ACCOUNT_ID:
    raise RuntimeError("R2 account id is not configured")

if not ACCESS_KEY or not SECRET_KEY:
    raise RuntimeError("R2 credentials are not configured")

if not BUCKET_NAME:
    raise RuntimeError("R2 bucket name is not configured")

if CHUNK_SIZE <= 0:
    raise RuntimeError("R2 object chunk size must be a positive integer in MB")

s3_client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION,
    config=Config(signature_version="s3v4"),
)


def ensure_bucket() -> None:
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        logger.info("Bucket exists", extra={"extra_data": {"bucket": BUCKET_NAME}})
        return
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code not in ("404", "NoSuchBucket", "NotFound"):
            logger.error(
                "Bucket check failed, skipping auto-creation (token may lack bucket-admin permissions)",
                extra={"extra_data": {"bucket": BUCKET_NAME, "errorCode": error_code}},
                exc_info=True,
            )
            return
    try:
        s3_client.create_bucket(Bucket=BUCKET_NAME)
        logger.info("Bucket created", extra={"extra_data": {"bucket": BUCKET_NAME}})
    except ClientError:
        logger.error("Failed to create bucket", extra={"extra_data": {"bucket": BUCKET_NAME}}, exc_info=True)
        raise

    apply_cors_configuration()


def apply_cors_configuration() -> None:
    """Browsers PUT parts directly to R2 with presigned URLs; without a bucket CORS
    policy the preflight fails and the upload never starts. ETag must be exposed so
    the browser can read it for the complete call."""
    cors_origins = [
        origin.strip()
        for origin in os.getenv("R2_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]
    cors_config = {
        "CORSRules": [
            {
                "AllowedOrigins": cors_origins,
                "AllowedMethods": ["PUT", "GET"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }
    try:
        s3_client.put_bucket_cors(Bucket=BUCKET_NAME, CORSConfiguration=cors_config)
        logger.info(
            "Bucket CORS policy applied",
            extra={"extra_data": {"bucket": BUCKET_NAME, "allowedOrigins": cors_origins}},
        )
    except ClientError:
        logger.warning(
            "Could not set bucket CORS policy (token may lack bucket-admin permissions). "
            "Browser uploads will fail until CORS is configured in the Cloudflare dashboard.",
            extra={"extra_data": {"bucket": BUCKET_NAME}},
            exc_info=True,
        )


def build_object_url(object_key: str) -> str:
    return f"{ENDPOINT}/{BUCKET_NAME}/{object_key}"


def download_url(object_key: str, filename: str) -> str:
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": object_key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=PRESIGN_EXPIRY_SECONDS,
    )


def _presign_part_urls(object_key: str, upload_id: str, total_parts: int) -> list:
    part_urls = []
    for part_num in range(1, total_parts + 1):
        url = s3_client.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": object_key,
                "UploadId": upload_id,
                "PartNumber": part_num,
            },
            ExpiresIn=PRESIGN_EXPIRY_SECONDS,
        )
        part_urls.append({"partNumber": part_num, "url": url})
    return part_urls


def _total_parts(file_size_bytes: int) -> int:
    total = max(1, math.ceil(file_size_bytes / (CHUNK_SIZE * 1024 * 1024)))
    if total > 10000:
        raise ValueError(f"file_size_bytes requires {total} parts, exceeds R2 limit of 10000")
    return total


def start_upload(object_key: str, file_size_bytes: int) -> dict:
    if file_size_bytes <= 0:
        raise ValueError("file_size_bytes must be greater than zero")

    total_parts = _total_parts(file_size_bytes)

    try:
        multipart_upload = s3_client.create_multipart_upload(Bucket=BUCKET_NAME, Key=object_key)
    except ClientError:
        logger.error(
            "Failed to create multipart upload",
            extra={"extra_data": {"objectKey": object_key, "fileSizeBytes": file_size_bytes}},
            exc_info=True,
        )
        raise

    upload_id = multipart_upload["UploadId"]
    logger.info(
        "Multipart upload created",
        extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id, "totalParts": total_parts}},
    )

    try:
        part_urls = _presign_part_urls(object_key, upload_id, total_parts)
    except ClientError:
        abort_upload(object_key, upload_id)
        logger.error(
            "Failed to generate presigned part URLs, multipart upload aborted",
            extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id}},
            exc_info=True,
        )
        raise

    return {
        "uploadId": upload_id,
        "objectKey": object_key,
        "chunkSize": CHUNK_SIZE,
        "partUrls": part_urls,
    }


def resume_part_urls(object_key: str, upload_id: str, file_size_bytes: int) -> dict:
    """Re-issue presigned part URLs for an existing multipart upload, without creating a new
    one. Used to replay a register request with the same idempotency key; previously issued
    URLs may have expired."""
    if file_size_bytes <= 0:
        raise ValueError("file_size_bytes must be greater than zero")

    total_parts = _total_parts(file_size_bytes)
    part_urls = _presign_part_urls(object_key, upload_id, total_parts)
    logger.info(
        "Presigned part URLs re-issued for existing multipart upload",
        extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id, "totalParts": total_parts}},
    )
    return {
        "uploadId": upload_id,
        "objectKey": object_key,
        "chunkSize": CHUNK_SIZE,
        "partUrls": part_urls,
    }


def head_object_etag(object_key: str) -> str | None:
    try:
        head = s3_client.head_object(Bucket=BUCKET_NAME, Key=object_key)
    except ClientError:
        logger.warning(
            "Object head failed",
            extra={"extra_data": {"objectKey": object_key}},
            exc_info=True,
        )
        return None
    return head["ETag"].strip('"')


def abort_upload(object_key: str, upload_id: str) -> None:
    try:
        s3_client.abort_multipart_upload(Bucket=BUCKET_NAME, Key=object_key, UploadId=upload_id)
        logger.info(
            "Multipart upload aborted",
            extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id}},
        )
    except ClientError:
        logger.error(
            "Failed to abort multipart upload",
            extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id}},
            exc_info=True,
        )


def delete_object(object_key: str) -> None:
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=object_key)
        logger.info("Object deleted", extra={"extra_data": {"objectKey": object_key}})
    except ClientError:
        logger.error(
            "Failed to delete object",
            extra={"extra_data": {"objectKey": object_key}},
            exc_info=True,
        )
        raise


def finish_upload(object_key: str, upload_id: str, uploaded_parts: list) -> dict:
    if not uploaded_parts:
        abort_upload(object_key, upload_id)
        raise ValueError("No uploaded parts provided")

    sorted_parts = sorted(uploaded_parts, key=lambda part: part["PartNumber"])

    try:
        result = s3_client.complete_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=object_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": sorted_parts},
        )
    except ClientError:
        logger.error(
            "Failed to complete multipart upload",
            extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id, "partCount": len(sorted_parts)}},
            exc_info=True,
        )
        raise

    try:
        head = s3_client.head_object(Bucket=BUCKET_NAME, Key=object_key)
    except ClientError:
        logger.error(
            "Completed upload but object head failed",
            extra={"extra_data": {"objectKey": object_key, "uploadId": upload_id}},
            exc_info=True,
        )
        raise

    final_url = build_object_url(object_key)
    logger.info(
        "Multipart upload completed",
        extra={"extra_data": {
            "objectKey": object_key,
            "uploadId": upload_id,
            "partCount": len(sorted_parts),
            "objectSize": head["ContentLength"],
            "objectEtag": head["ETag"],
            "finalUrl": final_url,
        }},
    )
    return {
        "finalUrl": final_url,
        "fileSize": head["ContentLength"],
        "etag": head["ETag"].strip('"'),
    }


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
