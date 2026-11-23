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


def build_object_url(object_key: str) -> str:
    return f"{ENDPOINT}/{BUCKET_NAME}/{object_key}"


def start_upload(object_key: str, file_size_bytes: int) -> dict:
    if file_size_bytes <= 0:
        raise ValueError("file_size_bytes must be greater than zero")

    total_parts = max(1, math.ceil(file_size_bytes / (CHUNK_SIZE * 1024 * 1024)))
    if total_parts > 10000:
        raise ValueError(f"file_size_bytes requires {total_parts} parts, exceeds R2 limit of 10000")

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

    part_urls = []
    try:
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
